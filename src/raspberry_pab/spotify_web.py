"""Spotify Web API (PKCE login) for browsing and searching in the Admin page.

Playback never goes through here; it stays on the local go-librespot API.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import SpotifyWebItem

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"
SCOPES = "playlist-read-private playlist-read-collaborative"
REFRESH_TOKEN_KEY = "spotify_refresh_token"
LOGIN_TTL_SECONDS = 600
SEARCH_TYPES = ("playlist", "album", "track", "artist")
SEARCH_LIMIT = 5  # per type; Spotify caps search at 10


class SpotifyWebError(Exception):
    """A Web API problem to show in the Admin page."""


class SpotifyNotConnectedError(SpotifyWebError):
    """No saved login (or Spotify revoked it)."""


@dataclass
class _PendingLogin:
    state: str
    verifier: str
    created_at: float


@dataclass
class _AccessToken:
    value: str
    expires_at: float


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _image(images: Any) -> str | None:
    if isinstance(images, list) and images and isinstance(images[-1], dict):
        # Images are sorted largest first; the smallest is enough for a list row.
        url = images[-1].get("url")
        return url if isinstance(url, str) else None
    return None


def _artists(item: dict[str, Any]) -> str:
    artists = item.get("artists") or []
    return ", ".join(a.get("name", "") for a in artists if isinstance(a, dict))


def to_web_item(kind: str, item: dict[str, Any]) -> SpotifyWebItem | None:
    """Map a Web API object to a list row; None for null/unplayable entries."""
    name = item.get("name")
    uri = item.get("uri")
    if not isinstance(name, str) or not isinstance(uri, str):
        return None
    subtitle = ""
    image = _image(item.get("images"))
    if kind == "playlist":
        owner = (item.get("owner") or {}).get("display_name") or ""
        total = (item.get("items") or item.get("tracks") or {}).get("total")
        parts = [p for p in (owner, f"{total} songs" if total is not None else "") if p]
        subtitle = " · ".join(parts)
    elif kind == "album":
        subtitle = _artists(item)
    elif kind == "track":
        subtitle = _artists(item)
        image = _image((item.get("album") or {}).get("images"))
    return SpotifyWebItem(
        kind=kind, name=name, uri=uri, subtitle=subtitle, image_url=image
    )


class SpotifyWebClient:
    """PKCE login with a stored refresh token; no client secret needed."""

    def __init__(
        self,
        settings: Settings,
        store: ScheduleStore,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._settings = settings
        self._store = store
        self._transport = transport
        self._clock = clock
        self._pending: _PendingLogin | None = None
        self._token: _AccessToken | None = None

    @property
    def configured(self) -> bool:
        return bool(self._settings.spotify_client_id)

    @property
    def connected(self) -> bool:
        return bool(self._store.get_setting(REFRESH_TOKEN_KEY))

    def start_login(self) -> str:
        """Return the Spotify authorize URL for a new PKCE login."""
        if not self.configured:
            raise SpotifyWebError("Set PAB_SPOTIFY_CLIENT_ID in .env first")
        verifier = secrets.token_urlsafe(64)
        state = secrets.token_urlsafe(16)
        self._pending = _PendingLogin(state, verifier, self._clock())
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._settings.spotify_client_id,
                "redirect_uri": self._settings.spotify_redirect_uri,
                "code_challenge_method": "S256",
                "code_challenge": code_challenge(verifier),
                "scope": SCOPES,
                "state": state,
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def finish_login_from_url(self, redirect_url: str) -> None:
        """Finish from the pasted redirect URL (login done on a phone)."""
        params = parse_qs(urlparse(redirect_url.strip()).query)
        await self.finish_login(
            code=(params.get("code") or [""])[0],
            state=(params.get("state") or [""])[0],
            error=(params.get("error") or [""])[0],
        )

    async def finish_login(self, *, code: str, state: str, error: str = "") -> None:
        pending = self._pending
        if error:
            raise SpotifyWebError(f"Spotify login was not approved ({error})")
        if (
            pending is None
            or not state
            or not secrets.compare_digest(state, pending.state)
            or self._clock() - pending.created_at > LOGIN_TTL_SECONDS
        ):
            raise SpotifyWebError("Login expired or unknown; tap Connect again")
        if not code:
            raise SpotifyWebError("No login code in that URL")
        self._pending = None
        data = await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._settings.spotify_redirect_uri,
                "client_id": self._settings.spotify_client_id,
                "code_verifier": pending.verifier,
            }
        )
        refresh = data.get("refresh_token")
        if not isinstance(refresh, str) or not refresh:
            raise SpotifyWebError("Spotify did not return a refresh token")
        self._store.set_setting(REFRESH_TOKEN_KEY, refresh)
        self._save_access_token(data)

    def disconnect(self) -> None:
        self._store.delete_setting(REFRESH_TOKEN_KEY)
        self._token = None

    async def my_playlists(self) -> list[SpotifyWebItem]:
        data = await self._get("/me/playlists", {"limit": 50})
        items = data.get("items") or []
        rows = [to_web_item("playlist", i) for i in items if isinstance(i, dict)]
        return [row for row in rows if row is not None]

    async def search(self, query: str) -> list[SpotifyWebItem]:
        cleaned = query.strip()
        if not cleaned:
            return []
        data = await self._get(
            "/search",
            {"q": cleaned, "type": ",".join(SEARCH_TYPES), "limit": SEARCH_LIMIT},
        )
        rows: list[SpotifyWebItem] = []
        for kind in SEARCH_TYPES:
            items = (data.get(f"{kind}s") or {}).get("items") or []
            for item in items:
                row = to_web_item(kind, item) if isinstance(item, dict) else None
                if row is not None:
                    rows.append(row)
        return rows

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        token = await self._access_token()
        response = await self._request(
            "GET",
            f"{API_BASE}{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 401:
            self._token = None
            raise SpotifyWebError("Spotify rejected the login; try again")
        if response.status_code == 429:
            raise SpotifyWebError("Spotify rate limit; wait a minute and retry")
        if not response.is_success:
            raise SpotifyWebError(f"Spotify error {response.status_code}")
        data = response.json()
        return data if isinstance(data, dict) else {}

    async def _access_token(self) -> str:
        if self._token is not None and self._clock() < self._token.expires_at:
            return self._token.value
        refresh = self._store.get_setting(REFRESH_TOKEN_KEY)
        if not refresh:
            raise SpotifyNotConnectedError("Spotify account not connected")
        try:
            data = await self._token_request(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": self._settings.spotify_client_id,
                }
            )
        except SpotifyNotConnectedError:
            self.disconnect()
            raise
        new_refresh = data.get("refresh_token")
        if isinstance(new_refresh, str) and new_refresh:
            self._store.set_setting(REFRESH_TOKEN_KEY, new_refresh)
        return self._save_access_token(data)

    def _save_access_token(self, data: dict[str, Any]) -> str:
        value = data.get("access_token")
        if not isinstance(value, str) or not value:
            raise SpotifyWebError("Spotify did not return an access token")
        expires_in = int(data.get("expires_in") or 3600)
        # Refresh a minute early so a request never races the expiry.
        self._token = _AccessToken(value, self._clock() + expires_in - 60)
        return value

    async def _token_request(self, form: dict[str, str]) -> dict[str, Any]:
        response = await self._request("POST", TOKEN_URL, data=form)
        if response.status_code == 400:
            try:
                error = response.json().get("error", "")
            except ValueError:
                error = ""
            if error == "invalid_grant":
                raise SpotifyNotConnectedError(
                    "Spotify login expired or was revoked; connect again"
                )
            raise SpotifyWebError(f"Spotify login failed ({error or 'bad request'})")
        if not response.is_success:
            raise SpotifyWebError(f"Spotify login failed ({response.status_code})")
        data = response.json()
        return data if isinstance(data, dict) else {}

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                timeout=10.0, transport=self._transport
            ) as client:
                return await client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            logger.warning("Spotify Web API %s %s failed: %s", method, url, exc)
            raise SpotifyWebError("Could not reach Spotify (no internet?)") from exc
