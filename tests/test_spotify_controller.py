"""Tests for the go-librespot controller, alert pause/resume, and music-break skip."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import httpx

from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import Alert, MusicBreakConfig, ReminderRule
from raspberry_pab.music_break_scheduler import MusicBreakScheduler
from raspberry_pab.music_breaks import save_config, was_slot_fired
from raspberry_pab.server import play_alert_groups
from raspberry_pab.spotify_controller import (
    ONLINE_CACHE_SECONDS,
    SpotifyController,
    parse_status,
)

PLAYING_STATUS: dict[str, Any] = {
    "username": "carlosvillalpando",
    "stopped": False,
    "paused": False,
    "volume": 60,
    "volume_steps": 100,
    "context_name": "Classical Piano",
    "context_uri": "spotify:playlist:37i9dQZF1DWUqIzZNMSCv3",
    "track": {
        "name": "III. Scherzo. Allegro vivace",
        "uri": "spotify:track:1XOwujGoAY7fsanvhQKfRz",
        "artist_names": ["Ludwig van Beethoven", "Igor Levit"],
        "album_cover_url": "https://i.scdn.co/image/abc",
    },
}


class FakeApi:
    """Records requests and replies like go-librespot."""

    def __init__(self, status: dict[str, Any] | None = None) -> None:
        self.status = status
        self.requests: list[tuple[str, str, Any]] = []
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("refused", request=request)
        body = json.loads(request.content) if request.content else None
        self.requests.append((request.method, request.url.path, body))
        if request.url.path == "/status":
            if self.status is None:
                return httpx.Response(204)
            return httpx.Response(200, json=self.status)
        if request.url.path == "/player/pause" and self.status is not None:
            self.status = {**self.status, "paused": True}
        if request.url.path == "/player/resume" and self.status is not None:
            self.status = {**self.status, "paused": False}
        return httpx.Response(200)

    def posts(self) -> list[str]:
        return [path for method, path, _ in self.requests if method == "POST"]


def _controller(
    tmp_path: Path,
    api: FakeApi,
    *,
    enabled: bool = True,
    **kwargs: Any,
) -> SpotifyController:
    store = ScheduleStore(tmp_path / "spotify.db")
    store.initialize()
    return SpotifyController(
        Settings(data_dir=tmp_path, spotify_enabled=enabled),
        store,
        transport=httpx.MockTransport(api.handler),
        **kwargs,
    )


def test_parse_status_playing_and_logged_out() -> None:
    playback = parse_status(PLAYING_STATUS)
    assert playback is not None
    assert playback.playing is True
    assert playback.track_name == "III. Scherzo. Allegro vivace"
    assert playback.artist_names == ("Ludwig van Beethoven", "Igor Levit")
    assert playback.context_name == "Classical Piano"
    assert parse_status({"stopped": True}) is None

    idle = parse_status({**PLAYING_STATUS, "stopped": True, "track": None})
    assert idle is not None
    assert idle.playing is False
    assert idle.track_name is None


def test_status_disabled_makes_no_request(tmp_path: Path) -> None:
    async def run() -> None:
        api = FakeApi(PLAYING_STATUS)
        controller = _controller(tmp_path, api, enabled=False)
        assert await controller.status() is None
        assert await controller.is_online() is False
        assert api.requests == []
        await controller.shutdown()

    asyncio.run(run())


def test_enabled_setting_overrides_env_default(tmp_path: Path) -> None:
    async def run() -> None:
        api = FakeApi(PLAYING_STATUS)
        controller = _controller(tmp_path, api, enabled=False)
        controller.set_enabled(True)
        assert controller.enabled() is True
        assert await controller.is_online() is True
        controller.set_enabled(False)
        assert await controller.is_online() is False
        await controller.shutdown()

    asyncio.run(run())


def test_status_204_and_unreachable_are_offline(tmp_path: Path) -> None:
    async def run() -> None:
        api = FakeApi(None)
        controller = _controller(tmp_path, api)
        assert await controller.status() is None
        assert controller.online_cached is False

        api.down = True
        assert await controller.status() is None
        assert await controller.pause() is False
        await controller.shutdown()

    asyncio.run(run())


def test_is_online_is_cached(tmp_path: Path) -> None:
    async def run() -> None:
        now = [100.0]
        api = FakeApi(PLAYING_STATUS)
        controller = _controller(tmp_path, api, clock=lambda: now[0])
        assert await controller.is_online() is True
        api.status = None
        now[0] += ONLINE_CACHE_SECONDS - 1
        assert await controller.is_online() is True
        now[0] += 2
        assert await controller.is_online() is False
        status_calls = [p for _, p, _ in api.requests if p == "/status"]
        assert len(status_calls) == 2
        await controller.shutdown()

    asyncio.run(run())


def test_is_online_follows_alert_sink_while_playing(tmp_path: Path) -> None:
    async def run() -> None:
        moved: list[str] = []

        def mover(sink: str) -> bool:
            moved.append(sink)
            return True

        api = FakeApi(PLAYING_STATUS)
        controller = _controller(
            tmp_path,
            api,
            sink_resolver=lambda: "bluez_output.50_F3_51_B4_8C_79.1",
            stream_mover=mover,
        )
        await controller.is_online()
        assert moved == ["bluez_output.50_F3_51_B4_8C_79.1"]
        await controller.shutdown()

    asyncio.run(run())


def test_play_and_volume_bodies(tmp_path: Path) -> None:
    async def run() -> None:
        api = FakeApi(PLAYING_STATUS)
        controller = _controller(tmp_path, api)
        assert await controller.play("spotify:playlist:abc") is True
        assert await controller.set_volume(45) is True
        assert ("POST", "/player/play", {"uri": "spotify:playlist:abc"}) in api.requests
        assert ("POST", "/player/volume", {"volume": 45}) in api.requests
        await controller.shutdown()

    asyncio.run(run())


def test_pause_for_alert_resumes_only_when_it_paused(tmp_path: Path) -> None:
    async def run() -> None:
        api = FakeApi(PLAYING_STATUS)
        controller = _controller(tmp_path, api)
        await controller.pause_for_alert()
        await controller.resume_after_alert()
        assert api.posts() == ["/player/pause", "/player/resume"]

        api.requests.clear()
        api.status = {**PLAYING_STATUS, "paused": True}
        await controller.pause_for_alert()
        await controller.resume_after_alert()
        assert api.posts() == []
        await controller.shutdown()

    asyncio.run(run())


def _rule() -> ReminderRule:
    return ReminderRule(
        id=7,
        offset_minutes=30,
        message_template="Warm Up {name}",
        led_enabled=True,
        led_red=1,
        led_green=2,
        led_blue=3,
        led_flash_duration_seconds=1,
        led_chase_duration_seconds=0,
    )


class _Log:
    def __init__(self) -> None:
        self.events: list[str] = []


def _alert_fakes(log: _Log, *, sound_fails: bool = False) -> dict[str, Any]:
    rule = _rule()

    class FakeStore:
        def get_rule(self, rule_id: int) -> ReminderRule | None:
            return rule

    class Effect:
        def __init__(self, name: str) -> None:
            self.name = name

        async def flash(self, _rule: ReminderRule) -> None:
            log.events.append(self.name)

        async def beep(self, _rule: ReminderRule) -> None:
            log.events.append(self.name)

        async def play(self, _rule: ReminderRule) -> None:
            log.events.append(self.name)
            if sound_fails:
                raise RuntimeError("no sink")

        async def show_sequence(self, _rule: ReminderRule, _msgs: list[str]) -> None:
            log.events.append(self.name)

    return {
        "store": FakeStore(),
        "led_controller": Effect("led"),
        "matrix_controller": Effect("matrix"),
        "buzzer_controller": Effect("buzzer"),
        "sound_controller": Effect("sound"),
    }


class FakeSpotify:
    def __init__(self, log: _Log) -> None:
        self.log = log

    async def pause_for_alert(self) -> None:
        self.log.events.append("spotify-pause")

    async def resume_after_alert(self) -> None:
        self.log.events.append("spotify-resume")


def test_play_alert_groups_pauses_and_resumes_spotify() -> None:
    async def run() -> None:
        log = _Log()
        await play_alert_groups(
            [[_group_alert()]],
            spotify_controller=FakeSpotify(log),  # type: ignore[arg-type]
            **_alert_fakes(log, sound_fails=True),
        )
        assert log.events[0] == "spotify-pause"
        assert log.events[-1] == "spotify-resume"
        assert "sound" in log.events

    asyncio.run(run())


def _group_alert() -> Alert:
    return Alert(
        id="1",
        participant_id=1,
        rule_id=7,
        name="Ada",
        event_date=date(2026, 8, 29),
        start_time=time(12, 0),
        start_at=datetime(2026, 8, 29, 12, 0),
        fire_at=datetime(2026, 8, 29, 11, 30),
        message="Warm Up Ada",
        created_at=datetime(2026, 8, 29, 11, 30),
    )


def test_music_break_skipped_while_spotify_online(tmp_path: Path) -> None:
    async def run() -> None:
        store = ScheduleStore(tmp_path / "music.db")
        store.initialize()
        save_config(
            store,
            MusicBreakConfig(
                enabled=True,
                sound_ids=[1],
                interval_minutes=15,
                start_time="09:00",
            ),
        )
        online = [True]

        async def skip_when() -> bool:
            return online[0]

        class Idle:
            async def stop(self) -> None:
                return None

        scheduler = MusicBreakScheduler(
            store,
            sound_controller=Idle(),  # type: ignore[arg-type]
            led_controller=Idle(),  # type: ignore[arg-type]
            matrix_controller=Idle(),  # type: ignore[arg-type]
            sound_path_resolver=lambda _id: None,
            skip_when=skip_when,
        )
        slot_time = datetime(2026, 8, 29, 9, 15)
        assert await scheduler.tick(slot_time) is False
        assert was_slot_fired(store, slot_time.date(), 1)
        assert scheduler._session_task is None

        online[0] = False
        # Same slot stays skipped (no late play); the next slot plays.
        assert await scheduler.tick(slot_time) is False
        started = await scheduler.tick(datetime(2026, 8, 29, 9, 30))
        assert started is True
        await scheduler.interrupt()

    asyncio.run(run())
