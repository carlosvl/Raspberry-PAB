"""A reminder rule's sound still plays when the rule fires (music breaks are gone)."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.models import Alert, ReminderRule
from raspberry_pab.server import create_app, play_alert_groups
from raspberry_pab.sound_controller import SoundController


class _Process:
    def poll(self) -> int | None:
        return 0

    def terminate(self) -> None:
        return None

    def kill(self) -> None:
        return None

    def wait(self, timeout: float | None = None) -> int:
        return 0


class _Noop:
    async def flash(self, _rule: ReminderRule) -> None:
        return None

    async def beep(self, _rule: ReminderRule) -> None:
        return None

    async def show_sequence(self, _rule: ReminderRule, _messages: list[str]) -> None:
        return None


def test_rule_sound_plays_when_rule_fires(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "raspberry_pab.sound_controller.shutil.which",
        lambda name: f"/usr/bin/{name}" if name == "pw-play" else None,
    )
    sound_file = tmp_path / "9.wav"
    sound_file.write_bytes(b"RIFF")
    rule = ReminderRule(
        id=3,
        offset_minutes=30,
        message_template="Warm Up {name}",
        sound_enabled=True,
        sound_id=9,
        sound_volume=50,
    )

    class Store:
        def get_rule(self, rule_id: int) -> ReminderRule | None:
            return rule if rule_id == 3 else None

    commands: list[list[str]] = []

    def player(command: list[str], _env: dict[str, str]) -> _Process:
        commands.append(command)
        return _Process()

    sounds = SoundController(
        Settings(sound_enabled=True),
        path_resolver=lambda sound_id: sound_file if sound_id == 9 else None,
        player_factory=player,
        sink_resolver=lambda _settings: "sink",
    )
    alert = Alert(
        id="1",
        participant_id=1,
        rule_id=3,
        name="Ada",
        event_date=date(2026, 8, 29),
        start_time=time(12, 0),
        start_at=datetime(2026, 8, 29, 12, 0),
        fire_at=datetime(2026, 8, 29, 11, 30),
        message="Warm Up Ada",
        created_at=datetime(2026, 8, 29, 11, 30),
    )

    async def run() -> None:
        await play_alert_groups(
            [[alert]],
            store=Store(),  # type: ignore[arg-type]
            led_controller=_Noop(),  # type: ignore[arg-type]
            matrix_controller=_Noop(),  # type: ignore[arg-type]
            buzzer_controller=_Noop(),  # type: ignore[arg-type]
            sound_controller=sounds,
        )
        await asyncio.sleep(0.05)
        await sounds.shutdown()

    asyncio.run(run())
    assert len(commands) == 1
    assert commands[0][-1] == str(sound_file)
    assert "--volume=0.5" in commands[0]


def test_music_break_api_is_gone(tmp_path: Path) -> None:
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (web_dir / "admin.html").write_text("<html></html>", encoding="utf-8")
    settings = Settings(data_dir=tmp_path / "data", web_dir=web_dir, admin_pin="9999")
    with TestClient(create_app(settings)) as client:
        headers = {"X-Admin-Pin": "9999"}
        assert client.get("/api/admin/music-breaks", headers=headers).status_code == 404
        assert client.get("/api/admin/sounds", headers=headers).status_code == 200
