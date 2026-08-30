"""Tests for music-break slot math, interrupt, and admin API."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import MusicBreakConfig
from raspberry_pab.music_break_scheduler import MusicBreakScheduler
from raspberry_pab.music_breaks import (
    current_slot_index,
    due_slot,
    next_slot_after,
    save_config,
)
from raspberry_pab.server import create_app


def test_slot_math_first_at_start_plus_interval() -> None:
    config = MusicBreakConfig(
        enabled=True,
        interval_minutes=15,
        start_time="09:00",
        sound_ids=[10, 20, 30],
    )
    assert current_slot_index(datetime(2026, 8, 29, 9, 14), config) is None
    assert due_slot(datetime(2026, 8, 29, 9, 14), config) is None

    slot = due_slot(datetime(2026, 8, 29, 9, 15), config)
    assert slot is not None
    assert slot.slot_index == 1
    assert slot.sound_id == 10
    assert slot.fire_at == datetime(2026, 8, 29, 9, 15)

    slot2 = due_slot(datetime(2026, 8, 29, 9, 30), config)
    assert slot2 is not None
    assert slot2.slot_index == 2
    assert slot2.sound_id == 20

    wrap = due_slot(datetime(2026, 8, 29, 10, 0), config)
    assert wrap is not None
    assert wrap.slot_index == 4
    assert wrap.sound_id == 10


def test_next_slot_before_first() -> None:
    config = MusicBreakConfig(
        enabled=True,
        interval_minutes=15,
        start_time="09:00",
        sound_ids=[7],
    )
    nxt = next_slot_after(datetime(2026, 8, 29, 8, 0), config)
    assert nxt is not None
    assert nxt.slot_index == 1
    assert nxt.fire_at == datetime(2026, 8, 29, 9, 15)


def test_music_break_interrupt_stops_sound(tmp_path: Path) -> None:
    async def run() -> None:
        class FakeSound:
            def __init__(self) -> None:
                self.stopped = 0

            async def stop(self) -> None:
                self.stopped += 1

            async def play_file(
                self, path: Path, *, volume: int = 80, wait: bool = False
            ) -> None:
                await asyncio.sleep(5)

        class FakeAnim:
            def __init__(self) -> None:
                self.stopped = 0

            async def stop(self) -> None:
                self.stopped += 1

            async def rainbow_pulse(
                self, *, pulse_ms: int, stop_event: asyncio.Event
            ) -> None:
                return None

        store = ScheduleStore(tmp_path / "music.db")
        store.initialize()
        save_config(
            store,
            MusicBreakConfig(enabled=True, sound_ids=[1], interval_minutes=15),
        )
        sound = FakeSound()
        led = FakeAnim()
        matrix = FakeAnim()
        scheduler = MusicBreakScheduler(
            store,
            sound_controller=sound,  # type: ignore[arg-type]
            led_controller=led,  # type: ignore[arg-type]
            matrix_controller=matrix,  # type: ignore[arg-type]
            sound_path_resolver=lambda _id: Path("/tmp/missing.wav"),
        )
        scheduler._playing = True
        scheduler._session_task = asyncio.create_task(asyncio.sleep(10))
        await scheduler.interrupt()
        assert sound.stopped >= 1
        assert led.stopped >= 1
        assert matrix.stopped >= 1
        assert scheduler.playing is False

    asyncio.run(run())


def test_music_breaks_api_round_trip(tmp_path: Path) -> None:
    web_dir = tmp_path / "web"
    (web_dir / "css").mkdir(parents=True)
    (web_dir / "js").mkdir()
    (web_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (web_dir / "admin.html").write_text("<html></html>", encoding="utf-8")
    (web_dir / "manifest.webmanifest").write_text("{}", encoding="utf-8")
    (web_dir / "sw.js").write_text("", encoding="utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        web_dir=web_dir,
        admin_pin="9999",
        sound_enabled=True,
    )
    store = ScheduleStore(settings.db_path)
    store.initialize()
    settings.sounds_dir.mkdir(parents=True, exist_ok=True)
    sound = store.create_sound(
        original_name="break.wav",
        stored_name="1.wav",
        content_type="audio/wav",
        size_bytes=12,
    )
    (settings.sounds_dir / "1.wav").write_bytes(b"RIFF........")

    with TestClient(create_app(settings)) as client:
        headers = {"X-Admin-Pin": "9999"}
        empty = client.get("/api/admin/music-breaks", headers=headers)
        assert empty.status_code == 200
        assert empty.json()["enabled"] is False

        updated = client.put(
            "/api/admin/music-breaks",
            headers=headers,
            json={
                "enabled": True,
                "interval_minutes": 15,
                "start_time": "09:00",
                "sound_ids": [sound.id],
                "volume": 70,
                "pulse_ms": 400,
            },
        )
        assert updated.status_code == 200, updated.text
        body = updated.json()
        assert body["enabled"] is True
        assert body["interval_minutes"] == 15
        assert body["sound_ids"] == [sound.id]
        assert body["volume"] == 70
        assert body["pulse_ms"] == 400
