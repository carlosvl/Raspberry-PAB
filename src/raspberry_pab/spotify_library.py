"""Saved Spotify playlists, share-link parsing, and the volume limit."""

from __future__ import annotations

import json
import re

from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import SpotifyPlaylist

SPOTIFY_PLAYLISTS_KEY = "spotify_playlists"
SPOTIFY_MAX_VOLUME_KEY = "spotify_max_volume"
DEFAULT_MAX_VOLUME = 80

_KINDS = ("playlist", "album", "track", "artist", "show", "episode")
_URI_RE = re.compile(rf"^spotify:({'|'.join(_KINDS)}):([A-Za-z0-9]{{10,40}})$")
_LINK_RE = re.compile(
    rf"^https?://open\.spotify\.com/(?:intl-[a-z-]+/)?({'|'.join(_KINDS)})/"
    r"([A-Za-z0-9]{10,40})(?:[/?#].*)?$"
)


def normalize_spotify_uri(value: str) -> str:
    """Accept a spotify: URI or an open.spotify.com link; return the URI."""
    cleaned = value.strip()
    match = _URI_RE.match(cleaned) or _LINK_RE.match(cleaned)
    if match is None:
        raise ValueError(f"Not a Spotify link or URI: {value!r}")
    return f"spotify:{match.group(1)}:{match.group(2)}"


def load_playlists(store: ScheduleStore) -> list[SpotifyPlaylist]:
    raw = store.get_setting(SPOTIFY_PLAYLISTS_KEY)
    if not raw:
        return []
    try:
        items = json.loads(raw)
        return [SpotifyPlaylist.model_validate(item) for item in items]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def save_playlists(store: ScheduleStore, playlists: list[SpotifyPlaylist]) -> None:
    store.set_setting(
        SPOTIFY_PLAYLISTS_KEY,
        json.dumps([item.model_dump(mode="json") for item in playlists]),
    )


def load_max_volume(store: ScheduleStore) -> int:
    raw = store.get_setting(SPOTIFY_MAX_VOLUME_KEY)
    try:
        value = int(raw) if raw else DEFAULT_MAX_VOLUME
    except ValueError:
        value = DEFAULT_MAX_VOLUME
    return max(0, min(100, value))


def save_max_volume(store: ScheduleStore, value: int) -> None:
    store.set_setting(SPOTIFY_MAX_VOLUME_KEY, str(max(0, min(100, value))))


def percent_to_steps(percent: int, volume_steps: int) -> int:
    return round(max(0, min(100, percent)) * volume_steps / 100)


def steps_to_percent(steps: int, volume_steps: int) -> int:
    if volume_steps <= 0:
        return 0
    return round(steps * 100 / volume_steps)
