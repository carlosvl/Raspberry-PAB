"""Loop "NOW PLAYING <song> - <artist>" on the matrix while Spotify plays."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import unicodedata

from raspberry_pab.db import ScheduleStore
from raspberry_pab.matrix_controller import (
    _ALLOWED_MESSAGE_CHARS,
    MAX_MATRIX_MESSAGE_CHARS,
    MatrixController,
)
from raspberry_pab.models import SpotifyMatrixConfig
from raspberry_pab.spotify_controller import SpotifyController, SpotifyPlayback
from raspberry_pab.spotify_library import load_matrix_config

logger = logging.getLogger(__name__)

NOW_PLAYING_PREFIX = "NOW PLAYING"
MAX_PASSES = 4
IDLE_POLL_SECONDS = 1.0
YIELD_SECONDS = 2.0
BETWEEN_LOOPS_SECONDS = 0.5

_BRACKETS = re.compile(r"\s*[(\[][^)\]]*[)\]]")
_VERSION_SUFFIX = re.compile(
    r"\s+-\s+.*\b(remaster(ed)?|live|version|edit|mix|mono|stereo)\b.*$",
    re.IGNORECASE,
)


def to_ascii(text: str) -> str:
    """Beyoncé -> Beyonce, curly quotes -> straight, drop other non-ASCII."""
    text = text.replace("’", "'").replace("‘", "'")
    decomposed = unicodedata.normalize("NFKD", text)
    return decomposed.encode("ascii", "ignore").decode("ascii")


def clean_title(title: str) -> str:
    """Drop (feat. …), [Live], " - Remastered 2011" style extras."""
    cleaned = _BRACKETS.sub("", title)
    cleaned = _VERSION_SUFFIX.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip() or title.strip()


def now_playing_text(playback: SpotifyPlayback) -> str | None:
    if not playback.track_name:
        return None
    title = to_ascii(clean_title(playback.track_name))
    artist = to_ascii(playback.artist_names[0]) if playback.artist_names else ""
    text = f"{NOW_PLAYING_PREFIX} {title}"
    if artist.strip():
        text += f" - {artist.strip()}"
    return text


def split_for_matrix(text: str, limit: int = MAX_MATRIX_MESSAGE_CHARS) -> list[str]:
    """Split into word-wrapped chunks the matrix firmware accepts (<= limit)."""
    # Same character filter as sanitize_matrix_message, without its 36-char cut.
    cleaned = re.sub(r"\s+", " ", _ALLOWED_MESSAGE_CHARS.sub(" ", text)).strip()
    words = cleaned.split(" ") if cleaned else []
    chunks: list[str] = []
    current = ""
    for word in words:
        while len(word) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(word[:limit])
            word = word[limit:]
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit:
            current = candidate
        else:
            chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks[:MAX_PASSES]


class NowPlayingMatrixTicker:
    """Lowest-priority matrix user: alerts and other scrolls interrupt it."""

    def __init__(
        self,
        store: ScheduleStore,
        *,
        matrix_controller: MatrixController,
        spotify_controller: SpotifyController,
        alerts_busy: asyncio.Event | None = None,
    ) -> None:
        self._store = store
        self._matrix = matrix_controller
        self._spotify = spotify_controller
        self._alerts_busy = alerts_busy
        self._task: asyncio.Task[None] | None = None
        self._paused = False
        self._scrolling = False

    @property
    def paused(self) -> bool:
        return self._paused

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="spotify-matrix-ticker")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def pause(self) -> None:
        """Hand the matrix to an alert right away."""
        self._paused = True
        if self._scrolling:
            await self._matrix.stop()

    def resume(self) -> None:
        self._paused = False

    def _blocked(self) -> bool:
        return (
            self._paused
            or (self._alerts_busy is not None and self._alerts_busy.is_set())
            or not self._matrix.is_available
            or self._matrix.is_busy
        )

    async def _run(self) -> None:
        while True:
            try:
                shown = await self.tick()
            except Exception:
                logger.exception("Now-playing matrix tick failed")
                shown = False
            await asyncio.sleep(BETWEEN_LOOPS_SECONDS if shown else IDLE_POLL_SECONDS)

    async def tick(self) -> bool:
        """Scroll the current song once (all chunks). False if nothing shown."""
        config = load_matrix_config(self._store)
        if not config.enabled or self._blocked():
            return False
        playback = await self._spotify.status()
        if playback is None or not playback.playing:
            return False
        text = now_playing_text(playback)
        if text is None:
            return False
        for chunk in split_for_matrix(text):
            if self._blocked():
                return False
            if not await self._scroll(chunk, config):
                return False
        return True

    async def _scroll(self, text: str, config: SpotifyMatrixConfig) -> bool:
        """One pass; False if another matrix user (alert, standings) took over."""
        self._scrolling = True
        try:
            await self._matrix.scroll_once(
                text,
                effect=config.effect,
                red=config.red,
                green=config.green,
                blue=config.blue,
            )
        except asyncio.CancelledError:
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise
            # Our pass was stopped by someone else: yield the matrix for a bit.
            await asyncio.sleep(YIELD_SECONDS)
            return False
        finally:
            self._scrolling = False
        return True
