"""Tests for the matrix NOW PLAYING loop."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from raspberry_pab.db import ScheduleStore
from raspberry_pab.matrix_controller import (
    MAX_MATRIX_MESSAGE_CHARS,
    sanitize_matrix_message,
)
from raspberry_pab.models import ReminderRule, SpotifyMatrixConfig
from raspberry_pab.server import play_alert_groups
from raspberry_pab.spotify_controller import SpotifyPlayback
from raspberry_pab.spotify_library import save_matrix_config
from raspberry_pab.spotify_matrix_ticker import (
    NowPlayingMatrixTicker,
    clean_title,
    now_playing_text,
    split_for_matrix,
    to_ascii,
)


def _playback(
    name: str | None = "Halo",
    artists: tuple[str, ...] = ("Beyonce",),
    *,
    paused: bool = False,
) -> SpotifyPlayback:
    return SpotifyPlayback(
        username="u",
        stopped=False,
        paused=paused,
        volume=50,
        volume_steps=100,
        track_name=name,
        artist_names=artists,
    )


class FakeSpotify:
    def __init__(self, playback: SpotifyPlayback | None) -> None:
        self.playback = playback

    async def status(self) -> SpotifyPlayback | None:
        return self.playback


class FakeMatrix:
    def __init__(self) -> None:
        self.scrolled: list[tuple[str, str, int, int, int]] = []
        self.stops = 0
        self.is_available = True
        self.is_busy = False
        self.block: asyncio.Event | None = None

    async def scroll_once(
        self, message: str, *, effect: str, red: int, green: int, blue: int
    ) -> None:
        self.scrolled.append((message, effect, red, green, blue))
        if self.block is not None:
            await self.block.wait()

    async def stop(self) -> None:
        self.stops += 1


def _ticker(
    tmp_path: Path,
    spotify: FakeSpotify,
    matrix: FakeMatrix,
    alerts_busy: asyncio.Event | None = None,
) -> NowPlayingMatrixTicker:
    store = ScheduleStore(tmp_path / "ticker.db")
    store.initialize()
    return NowPlayingMatrixTicker(
        store,
        matrix_controller=matrix,  # type: ignore[arg-type]
        spotify_controller=spotify,  # type: ignore[arg-type]
        alerts_busy=alerts_busy,
    )


def test_text_cleanup() -> None:
    assert to_ascii("Beyoncé – Déjà Vu’s") == "Beyonce  Deja Vu's"
    assert clean_title("Halo (feat. Someone) [Live]") == "Halo"
    assert clean_title("Yesterday - Remastered 2009") == "Yesterday"
    assert clean_title("Fade - Into You") == "Fade - Into You"
    text = now_playing_text(
        _playback("Crazy In Love (feat. JAY-Z)", ("Beyoncé", "JAY-Z"))
    )
    assert text == "NOW PLAYING Crazy In Love - Beyonce"
    assert now_playing_text(_playback(None)) is None


def test_split_keeps_every_chunk_within_firmware_limit() -> None:
    long_title = (
        'Symphony No. 3 in E-Flat Major, Op. 55 "Eroica" '
        "(Transcr. for Piano by Franz Liszt, S. 464/3): III. Scherzo. Allegro vivace"
    )
    text = now_playing_text(
        _playback(long_title, ("Ludwig van Beethoven", "Igor Levit"))
    )
    assert text is not None
    chunks = split_for_matrix(text)
    assert chunks[0].startswith("NOW PLAYING Symphony")
    assert chunks[-1].endswith("Beethoven")
    for chunk in chunks:
        assert len(chunk) <= MAX_MATRIX_MESSAGE_CHARS
        assert sanitize_matrix_message(chunk) == chunk
    assert split_for_matrix("NOW PLAYING " + "X" * 50) == [
        "NOW PLAYING",
        "X" * MAX_MATRIX_MESSAGE_CHARS,
        "X" * (50 - MAX_MATRIX_MESSAGE_CHARS),
    ]


def test_tick_scrolls_while_playing_with_config(tmp_path: Path) -> None:
    async def run() -> None:
        matrix = FakeMatrix()
        ticker = _ticker(tmp_path, FakeSpotify(_playback()), matrix)
        assert await ticker.tick() is True
        assert matrix.scrolled == [("NOW PLAYING Halo - Beyonce", "solid", 30, 215, 96)]

        save_matrix_config(
            ticker._store,
            SpotifyMatrixConfig(effect="rainbow", red=1, green=2, blue=3),
        )
        await ticker.tick()
        assert matrix.scrolled[-1][1:] == ("rainbow", 1, 2, 3)

    asyncio.run(run())


def test_tick_idle_when_not_playing_disabled_or_blocked(tmp_path: Path) -> None:
    async def run() -> None:
        matrix = FakeMatrix()
        spotify = FakeSpotify(_playback(paused=True))
        busy = asyncio.Event()
        ticker = _ticker(tmp_path, spotify, matrix, alerts_busy=busy)
        assert await ticker.tick() is False  # paused
        spotify.playback = None
        assert await ticker.tick() is False  # offline
        spotify.playback = _playback()

        save_matrix_config(ticker._store, SpotifyMatrixConfig(enabled=False))
        assert await ticker.tick() is False
        save_matrix_config(ticker._store, SpotifyMatrixConfig())

        busy.set()
        assert await ticker.tick() is False
        busy.clear()
        matrix.is_busy = True  # e.g. a team-standings scroll
        assert await ticker.tick() is False
        matrix.is_busy = False
        matrix.is_available = False
        assert await ticker.tick() is False
        assert matrix.scrolled == []

    asyncio.run(run())


def test_pause_stops_current_pass_and_resume_uses_current_song(tmp_path: Path) -> None:
    async def run() -> None:
        matrix = FakeMatrix()
        matrix.block = asyncio.Event()
        spotify = FakeSpotify(_playback("Halo"))
        ticker = _ticker(tmp_path, spotify, matrix)
        running = asyncio.create_task(ticker.tick())
        await asyncio.sleep(0)
        await ticker.pause()
        assert matrix.stops == 1
        matrix.block.set()
        await running

        assert await ticker.tick() is False  # still paused
        spotify.playback = _playback("Formation")
        ticker.resume()
        matrix.block = None
        assert await ticker.tick() is True
        assert matrix.scrolled[-1][0] == "NOW PLAYING Formation - Beyonce"

    asyncio.run(run())


def test_outside_cancel_yields_instead_of_exiting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("raspberry_pab.spotify_matrix_ticker.YIELD_SECONDS", 0)

    async def run() -> None:
        class CancellingMatrix(FakeMatrix):
            async def scroll_once(
                self, message: str, *, effect: str, red: int, green: int, blue: int
            ) -> None:
                self.scrolled.append((message, effect, red, green, blue))
                raise asyncio.CancelledError  # another user called matrix.stop()

        matrix = CancellingMatrix()
        ticker = _ticker(tmp_path, FakeSpotify(_playback()), matrix)
        assert await ticker.tick() is False
        assert await ticker.tick() is False
        assert len(matrix.scrolled) == 2

    asyncio.run(run())


def test_play_alert_groups_pauses_and_resumes_ticker() -> None:
    async def run() -> None:
        events: list[str] = []

        class Ticker:
            async def pause(self) -> None:
                events.append("ticker-pause")

            def resume(self) -> None:
                events.append("ticker-resume")

        class Store:
            def get_rule(self, _rule_id: int) -> ReminderRule | None:
                return None

        await play_alert_groups(
            [[]],
            store=Store(),  # type: ignore[arg-type]
            led_controller=Any,  # type: ignore[arg-type]
            matrix_controller=Any,  # type: ignore[arg-type]
            buzzer_controller=Any,  # type: ignore[arg-type]
            sound_controller=Any,  # type: ignore[arg-type]
            now_playing_ticker=Ticker(),  # type: ignore[arg-type]
        )
        assert events == ["ticker-pause", "ticker-resume"]

    asyncio.run(run())
