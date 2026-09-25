"""Tests for the Spotify Web API client (PKCE login, playlists, search)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.server import create_app
from raspberry_pab.spotify_web import (
    REFRESH_TOKEN_KEY,
    SpotifyNotConnectedError,
    SpotifyWebClient,
    SpotifyWebError,
    code_challenge,
)

HEADERS = {"X-Admin-Pin": "9999"}
REDIRECT = "http://127.0.0.1:8080/api/spotify/callback"

PLAYLIST = {
    "name": "Race Day",
    "uri": "spotify:playlist:37i9dQZF1DWUqIzZNMSCv3",
    "owner": {"display_name": "carlos"},
    "items": {"total": 42},
    "images": [{"url": "https://i.scdn.co/big"}, {"url": "https://i.scdn.co/small"}],
}


class FakeSpotify:
    """Fake accounts.spotify.com + api.spotify.com."""

    def __init__(self) -> None:
        self.token_forms: list[dict[str, str]] = []
        self.api_calls: list[tuple[str, dict[str, str], str]] = []
        self.refresh_error: str | None = None
        self.rotate_refresh = False
        self.counter = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "accounts.spotify.com":
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            self.token_forms.append(form)
            if form["grant_type"] == "refresh_token" and self.refresh_error:
                return httpx.Response(400, json={"error": self.refresh_error})
            self.counter += 1
            body: dict[str, Any] = {
                "access_token": f"access-{self.counter}",
                "expires_in": 3600,
            }
            if form["grant_type"] == "authorization_code" or self.rotate_refresh:
                body["refresh_token"] = f"refresh-{self.counter}"
            return httpx.Response(200, json=body)
        params = dict(request.url.params)
        auth = request.headers.get("Authorization", "")
        self.api_calls.append((request.url.path, params, auth))
        if request.url.path == "/v1/me/playlists":
            return httpx.Response(200, json={"items": [PLAYLIST, None]})
        if request.url.path == "/v1/search":
            return httpx.Response(
                200,
                json={
                    "playlists": {"items": [None, PLAYLIST]},
                    "albums": {
                        "items": [
                            {
                                "name": "Lemonade",
                                "uri": "spotify:album:7dK54iZuOxXFarGhXwEXfF",
                                "artists": [{"name": "Beyonce"}],
                                "images": [],
                            }
                        ]
                    },
                    "tracks": {
                        "items": [
                            {
                                "name": "Formation",
                                "uri": "spotify:track:6g0Orsxv6glTJCt4cHsRsQ",
                                "artists": [{"name": "Beyonce"}],
                                "album": {"images": [{"url": "https://i.scdn.co/a"}]},
                            }
                        ]
                    },
                    "artists": {"items": []},
                },
            )
        return httpx.Response(404)


def _store(tmp_path: Path) -> ScheduleStore:
    store = ScheduleStore(tmp_path / "web.db")
    store.initialize()
    return store


def _client(
    tmp_path: Path, fake: FakeSpotify, *, client_id: str = "abc123", **kwargs: Any
) -> SpotifyWebClient:
    return SpotifyWebClient(
        Settings(data_dir=tmp_path, spotify_client_id=client_id),
        _store(tmp_path),
        transport=httpx.MockTransport(fake.handler),
        **kwargs,
    )


def _login(client: SpotifyWebClient) -> dict[str, str]:
    url = client.start_login()
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def test_code_challenge_matches_rfc7636_example() -> None:
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert code_challenge(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_start_login_builds_pkce_url(tmp_path: Path) -> None:
    client = _client(tmp_path, FakeSpotify())
    params = _login(client)
    assert params["client_id"] == "abc123"
    assert params["redirect_uri"] == REDIRECT
    assert params["code_challenge_method"] == "S256"
    assert params["response_type"] == "code"
    assert "playlist-read-private" in params["scope"]
    assert params["state"]


def test_start_login_requires_client_id(tmp_path: Path) -> None:
    client = _client(tmp_path, FakeSpotify(), client_id="")
    assert client.configured is False
    with pytest.raises(SpotifyWebError):
        client.start_login()


def test_login_from_pasted_url_stores_refresh_token(tmp_path: Path) -> None:
    async def run() -> None:
        fake = FakeSpotify()
        client = _client(tmp_path, fake)
        params = _login(client)
        await client.finish_login_from_url(
            f"{REDIRECT}?code=the-code&state={params['state']}"
        )
        assert client.connected is True
        form = fake.token_forms[0]
        assert form["grant_type"] == "authorization_code"
        assert form["code"] == "the-code"
        assert form["redirect_uri"] == REDIRECT
        assert code_challenge(form["code_verifier"]) == params["code_challenge"]
        assert "client_secret" not in form
        assert client._store.get_setting(REFRESH_TOKEN_KEY) == "refresh-1"

    asyncio.run(run())


def test_login_rejects_wrong_state_denied_or_expired(tmp_path: Path) -> None:
    async def run() -> None:
        now = [1000.0]
        client = _client(tmp_path, FakeSpotify(), clock=lambda: now[0])
        params = _login(client)
        with pytest.raises(SpotifyWebError):
            await client.finish_login(code="c", state="wrong")
        with pytest.raises(SpotifyWebError, match="not approved"):
            await client.finish_login(
                code="", state=params["state"], error="access_denied"
            )
        now[0] += 601
        with pytest.raises(SpotifyWebError, match="expired"):
            await client.finish_login(code="c", state=params["state"])
        assert client.connected is False

    asyncio.run(run())


def test_playlists_and_search_refresh_token_once(tmp_path: Path) -> None:
    async def run() -> None:
        fake = FakeSpotify()
        client = _client(tmp_path, fake)
        client._store.set_setting(REFRESH_TOKEN_KEY, "saved-refresh")

        playlists = await client.my_playlists()
        assert [p.name for p in playlists] == ["Race Day"]
        assert playlists[0].subtitle == "carlos · 42 songs"
        assert playlists[0].image_url == "https://i.scdn.co/small"

        results = await client.search("beyonce")
        assert [(r.kind, r.name) for r in results] == [
            ("playlist", "Race Day"),
            ("album", "Lemonade"),
            ("track", "Formation"),
        ]
        assert results[2].image_url == "https://i.scdn.co/a"
        search_params = fake.api_calls[-1][1]
        assert search_params["type"] == "playlist,album,track,artist"
        assert int(search_params["limit"]) <= 10

        refreshes = [f for f in fake.token_forms if f["grant_type"] == "refresh_token"]
        assert len(refreshes) == 1
        assert refreshes[0]["refresh_token"] == "saved-refresh"
        assert all(auth == "Bearer access-1" for _, _, auth in fake.api_calls)

    asyncio.run(run())


def test_rotated_refresh_token_is_saved(tmp_path: Path) -> None:
    async def run() -> None:
        fake = FakeSpotify()
        fake.rotate_refresh = True
        client = _client(tmp_path, fake)
        client._store.set_setting(REFRESH_TOKEN_KEY, "old")
        await client.my_playlists()
        assert client._store.get_setting(REFRESH_TOKEN_KEY) == "refresh-1"

    asyncio.run(run())


def test_revoked_refresh_disconnects(tmp_path: Path) -> None:
    async def run() -> None:
        fake = FakeSpotify()
        fake.refresh_error = "invalid_grant"
        client = _client(tmp_path, fake)
        client._store.set_setting(REFRESH_TOKEN_KEY, "revoked")
        with pytest.raises(SpotifyNotConnectedError):
            await client.my_playlists()
        assert client.connected is False

    asyncio.run(run())


def _app_client(tmp_path: Path, fake: FakeSpotify) -> TestClient:
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (web_dir / "admin.html").write_text("<html></html>", encoding="utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        web_dir=web_dir,
        admin_pin="9999",
        spotify_client_id="abc123",
    )
    app = create_app(settings)
    app.state.spotify_web = SpotifyWebClient(
        settings,
        app.state.schedule_store,
        transport=httpx.MockTransport(fake.handler),
    )
    return TestClient(app)


def test_web_routes_login_callback_and_search(tmp_path: Path) -> None:
    fake = FakeSpotify()
    with _app_client(tmp_path, fake) as client:
        assert client.get("/api/admin/spotify/web").status_code == 401
        status = client.get("/api/admin/spotify/web", headers=HEADERS).json()
        assert status == {
            "configured": True,
            "connected": False,
            "redirect_uri": REDIRECT,
        }
        not_connected = client.get("/api/admin/spotify/web/playlists", headers=HEADERS)
        assert not_connected.status_code == 409

        url = client.post("/api/admin/spotify/web/login", headers=HEADERS).json()[
            "authorize_url"
        ]
        state = parse_qs(urlparse(url).query)["state"][0]
        page = client.get(f"/api/spotify/callback?code=c1&state={state}")
        assert page.status_code == 200
        assert "Spotify connected" in page.text

        replay = client.get(f"/api/spotify/callback?code=c1&state={state}")
        assert replay.status_code == 400

        results = client.get(
            "/api/admin/spotify/web/search", params={"q": "beyonce"}, headers=HEADERS
        ).json()
        assert results[0]["uri"] == "spotify:playlist:37i9dQZF1DWUqIzZNMSCv3"

        status = client.delete("/api/admin/spotify/web", headers=HEADERS).json()
        assert status["connected"] is False


def test_web_complete_from_pasted_url(tmp_path: Path) -> None:
    with _app_client(tmp_path, FakeSpotify()) as client:
        url = client.post("/api/admin/spotify/web/login", headers=HEADERS).json()[
            "authorize_url"
        ]
        state = parse_qs(urlparse(url).query)["state"][0]
        bad = client.post(
            "/api/admin/spotify/web/complete",
            headers=HEADERS,
            json={"redirect_url": f"{REDIRECT}?code=c&state=nope"},
        )
        assert bad.status_code == 400
        ok = client.post(
            "/api/admin/spotify/web/complete",
            headers=HEADERS,
            json={"redirect_url": f"{REDIRECT}?code=c&state={state}"},
        )
        assert ok.json()["connected"] is True
