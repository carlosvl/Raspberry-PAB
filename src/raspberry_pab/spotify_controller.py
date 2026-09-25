"""Control the local go-librespot Spotify Connect receiver over its HTTP API."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from raspberry_pab.audio_sink import _runtime_env, list_sink_names
from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore

logger = logging.getLogger(__name__)

SPOTIFY_ENABLED_KEY = "spotify_enabled"
GO_LIBRESPOT_APP_NAME = "go-librespot"
ONLINE_CACHE_SECONDS = 10.0
REQUEST_TIMEOUT_SECONDS = 1.5

SinkResolver = Callable[[], str | None]
StreamMover = Callable[[str], bool]


@dataclass(frozen=True)
class SpotifyPlayback:
    """Snapshot of go-librespot /status for a logged-in session."""

    username: str
    stopped: bool
    paused: bool
    volume: int
    volume_steps: int
    context_name: str | None = None
    context_uri: str | None = None
    track_name: str | None = None
    track_uri: str | None = None
    artist_names: tuple[str, ...] = ()
    album_cover_url: str | None = None

    @property
    def playing(self) -> bool:
        return not self.stopped and not self.paused


def parse_status(data: dict[str, Any]) -> SpotifyPlayback | None:
    """Build a playback snapshot from /status JSON; None without a session."""
    username = data.get("username")
    if not isinstance(username, str) or not username:
        return None
    track = data.get("track")
    track_data: dict[str, Any] = track if isinstance(track, dict) else {}
    artists = track_data.get("artist_names")
    names = tuple(str(a) for a in artists) if isinstance(artists, list) else ()
    return SpotifyPlayback(
        username=username,
        stopped=bool(data.get("stopped", True)),
        paused=bool(data.get("paused", False)),
        volume=int(data.get("volume") or 0),
        volume_steps=int(data.get("volume_steps") or 100),
        context_name=data.get("context_name"),
        context_uri=data.get("context_uri"),
        track_name=track_data.get("name"),
        track_uri=track_data.get("uri"),
        artist_names=names,
        album_cover_url=track_data.get("album_cover_url"),
    )


def find_app_sink_input(app_name: str) -> tuple[int, int] | None:
    """Return (sink_input_index, sink_index) of the first stream named app_name."""
    if not shutil.which("pactl"):
        return None
    try:
        result = subprocess.run(
            ["pactl", "-f", "json", "list", "sink-inputs"],
            check=False,
            capture_output=True,
            text=True,
            env=_runtime_env(),
            timeout=5,
        )
        inputs = json.loads(result.stdout) if result.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    for item in inputs:
        props = item.get("properties") or {}
        if props.get("application.name") == app_name:
            return int(item["index"]), int(item["sink"])
    return None


def sink_index_by_name() -> dict[str, int]:
    if not shutil.which("pactl"):
        return {}
    try:
        result = subprocess.run(
            ["pactl", "-f", "json", "list", "sinks"],
            check=False,
            capture_output=True,
            text=True,
            env=_runtime_env(),
            timeout=5,
        )
        sinks = json.loads(result.stdout) if result.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {}
    return {str(s["name"]): int(s["index"]) for s in sinks if "name" in s}


def move_go_librespot_stream(sink: str) -> bool:
    """Move the go-librespot stream to sink; True if moved (or already there)."""
    if sink not in list_sink_names():
        return False
    found = find_app_sink_input(GO_LIBRESPOT_APP_NAME)
    if found is None:
        return False
    input_index, current_sink = found
    if sink_index_by_name().get(sink) == current_sink:
        return True
    try:
        result = subprocess.run(
            ["pactl", "move-sink-input", str(input_index), sink],
            check=False,
            capture_output=True,
            text=True,
            env=_runtime_env(),
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode == 0:
        logger.info("Moved Spotify stream to sink %s", sink)
        return True
    return False


class SpotifyController:
    """Talks to go-librespot; every call fails quietly so alerts never break."""

    def __init__(
        self,
        settings: Settings,
        store: ScheduleStore,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sink_resolver: SinkResolver | None = None,
        stream_mover: StreamMover | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._store = store
        self._transport = transport
        self._sink_resolver = sink_resolver
        self._stream_mover = stream_mover or move_go_librespot_stream
        self._clock = clock
        self._client: httpx.AsyncClient | None = None
        self._online = False
        self._online_checked_at: float | None = None
        self._paused_by_alert = False
        self._watch_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Refresh online state and follow the alert sink in the background."""
        if self._watch_task is None or self._watch_task.done():
            self._watch_task = asyncio.create_task(self._watch(), name="spotify-watch")

    async def _watch(self) -> None:
        while True:
            try:
                await self.is_online()
            except Exception:
                logger.exception("Spotify status refresh failed")
            await asyncio.sleep(ONLINE_CACHE_SECONDS)

    @property
    def online_cached(self) -> bool:
        """Last known online state (no request)."""
        return self._online

    def enabled(self) -> bool:
        raw = self._store.get_setting(SPOTIFY_ENABLED_KEY)
        if raw is None or raw == "":
            return self._settings.spotify_enabled
        return raw == "1"

    def set_enabled(self, enabled: bool) -> None:
        self._store.set_setting(SPOTIFY_ENABLED_KEY, "1" if enabled else "0")
        self._online_checked_at = None

    async def status(self) -> SpotifyPlayback | None:
        """Fetch /status; None when disabled, unreachable, or not logged in."""
        playback: SpotifyPlayback | None = None
        if self.enabled():
            response = await self._request("GET", "/status")
            if response is not None and response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    data = None
                if isinstance(data, dict):
                    playback = parse_status(data)
        self._online = playback is not None
        self._online_checked_at = self._clock()
        return playback

    async def is_online(self) -> bool:
        """Cached online check, refreshed every ONLINE_CACHE_SECONDS."""
        checked = self._online_checked_at
        if checked is not None and self._clock() - checked < ONLINE_CACHE_SECONDS:
            return self._online
        playback = await self.status()
        if playback is not None and playback.playing:
            await self.follow_sink()
        return self._online

    async def follow_sink(self) -> bool:
        """Move the Spotify stream to the same sink alerts use."""
        if self._sink_resolver is None:
            return False
        sink = self._sink_resolver()
        if not sink:
            return False
        try:
            return await asyncio.to_thread(self._stream_mover, sink)
        except Exception:
            logger.exception("Moving Spotify stream to %s failed", sink)
            return False

    async def play(self, uri: str, *, skip_to_uri: str | None = None) -> bool:
        body: dict[str, Any] = {"uri": uri}
        if skip_to_uri:
            body["skip_to_uri"] = skip_to_uri
        return await self._post("/player/play", body)

    async def pause(self) -> bool:
        return await self._post("/player/pause")

    async def resume(self) -> bool:
        return await self._post("/player/resume")

    async def next(self) -> bool:
        return await self._post("/player/next")

    async def prev(self) -> bool:
        return await self._post("/player/prev")

    async def set_volume(self, volume: int) -> bool:
        return await self._post("/player/volume", {"volume": max(0, volume)})

    async def pause_for_alert(self) -> None:
        """Pause Spotify if it is playing; remember to resume afterward."""
        if self._paused_by_alert:
            return
        playback = await self.status()
        if playback is None or not playback.playing:
            return
        self._paused_by_alert = await self.pause()

    async def resume_after_alert(self) -> None:
        """Resume only if pause_for_alert paused it."""
        if not self._paused_by_alert:
            return
        self._paused_by_alert = False
        await self.follow_sink()
        await self.resume()

    async def shutdown(self) -> None:
        if self._watch_task is not None:
            self._watch_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watch_task
            self._watch_task = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _post(self, path: str, body: dict[str, Any] | None = None) -> bool:
        if not self.enabled():
            return False
        response = await self._request("POST", path, body)
        return response is not None and response.is_success

    async def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> httpx.Response | None:
        try:
            return await self._get_client().request(method, path, json=body)
        except httpx.HTTPError as exc:
            logger.debug("Spotify API %s %s failed: %s", method, path, exc)
            return None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.spotify_api_url,
                timeout=REQUEST_TIMEOUT_SECONDS,
                transport=self._transport,
            )
        return self._client
