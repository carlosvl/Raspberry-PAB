"""Spotify Jam link shown as a QR code on the kiosk board.

Spotify's public API has no Jam feature and go-librespot doesn't report one, so
the Pi can't detect a Jam. The admin pastes the Jam share link instead, and the
board shows its QR code until it is cleared.
"""

from __future__ import annotations

import io
from urllib.parse import urlsplit

import segno

from raspberry_pab.db import ScheduleStore

SPOTIFY_JAM_URL_KEY = "spotify_jam_url"
MAX_URL_LENGTH = 500
_ALLOWED_HOSTS = ("spotify.link", "spotify.app.link", "spotify.com")


def normalize_jam_url(raw: str) -> str:
    """Return a clean Spotify https link, or raise ValueError.

    The kiosk is public, so only Spotify hosts may end up in a QR code.
    """
    cleaned = raw.strip()
    if not cleaned or len(cleaned) > MAX_URL_LENGTH:
        raise ValueError("Paste the Jam link from the Spotify app")
    parts = urlsplit(cleaned)
    host = (parts.hostname or "").lower()
    allowed = any(host == h or host.endswith(f".{h}") for h in _ALLOWED_HOSTS)
    if parts.scheme != "https" or not allowed:
        raise ValueError("That isn't a Spotify https link")
    return cleaned


def load_jam_url(store: ScheduleStore) -> str | None:
    raw = store.get_setting(SPOTIFY_JAM_URL_KEY)
    return raw.strip() if raw and raw.strip() else None


def save_jam_url(store: ScheduleStore, url: str) -> None:
    store.set_setting(SPOTIFY_JAM_URL_KEY, url)


def clear_jam_url(store: ScheduleStore) -> None:
    store.set_setting(SPOTIFY_JAM_URL_KEY, "")


def qr_svg(url: str) -> str:
    """Inline SVG QR code (error level M, 2-module quiet zone).

    It has a viewBox and no fixed size, so CSS can scale it.
    """
    buffer = io.BytesIO()
    segno.make(url, error="m").save(
        buffer,
        kind="svg",
        scale=1,
        border=2,
        xmldecl=False,
        svgns=True,
        omitsize=True,
    )
    svg = buffer.getvalue().decode("utf-8")
    return svg.replace("<svg ", '<svg shape-rendering="crispEdges" ', 1)
