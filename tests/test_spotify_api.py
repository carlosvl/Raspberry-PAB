"""Tests for the admin Spotify API and saved-playlist helpers."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from tests.test_spotify_controller import PLAYING_STATUS, FakeApi

from raspberry_pab.config import Settings
from raspberry_pab.server import create_app
from raspberry_pab.spotify_controller import SpotifyController
from raspberry_pab.spotify_library import normalize_spotify_uri

HEADERS = {"X-Admin-Pin": "9999"}


def _client(tmp_path: Path, api: FakeApi) -> TestClient:
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (web_dir / "admin.html").write_text("<html></html>", encoding="utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        web_dir=web_dir,
        admin_pin="9999",
        spotify_enabled=True,
        spotify_api_url="http://spotify.test",
    )
    app = create_app(settings)
    app.state.spotify_controller = SpotifyController(
        settings,
        app.state.schedule_store,
        transport=httpx.MockTransport(api.handler),
    )
    return TestClient(app)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "spotify:playlist:37i9dQZF1DWUqIzZNMSCv3",
            "spotify:playlist:37i9dQZF1DWUqIzZNMSCv3",
        ),
        (
            "https://open.spotify.com/playlist/37i9dQZF1DWUqIzZNMSCv3?si=abc123",
            "spotify:playlist:37i9dQZF1DWUqIzZNMSCv3",
        ),
        (
            "https://open.spotify.com/intl-es/album/1XOwujGoAY7fsanvhQKfRz",
            "spotify:album:1XOwujGoAY7fsanvhQKfRz",
        ),
    ],
)
def test_normalize_spotify_uri(value: str, expected: str) -> None:
    assert normalize_spotify_uri(value) == expected


def test_normalize_spotify_uri_rejects_other_links() -> None:
    with pytest.raises(ValueError):
        normalize_spotify_uri("https://example.com/playlist/abc")


def test_spotify_routes_require_pin(tmp_path: Path) -> None:
    with _client(tmp_path, FakeApi(PLAYING_STATUS)) as client:
        assert client.get("/api/admin/spotify").status_code == 401


def test_spotify_status_reports_now_playing(tmp_path: Path) -> None:
    with _client(tmp_path, FakeApi(PLAYING_STATUS)) as client:
        body = client.get("/api/admin/spotify", headers=HEADERS).json()
    assert body["online"] is True
    assert body["playing"] is True
    assert body["track_name"] == "III. Scherzo. Allegro vivace"
    assert body["artist_names"][0] == "Ludwig van Beethoven"
    assert body["volume"] == 60
    assert body["max_volume"] == 80


def test_spotify_offline_status_and_503_on_actions(tmp_path: Path) -> None:
    api = FakeApi(None)
    api.down = True
    with _client(tmp_path, api) as client:
        body = client.get("/api/admin/spotify", headers=HEADERS).json()
        assert body["online"] is False
        response = client.post("/api/admin/spotify/player/pause", headers=HEADERS)
        assert response.status_code == 503


def test_player_actions_and_volume_cap(tmp_path: Path) -> None:
    api = FakeApi(PLAYING_STATUS)
    with _client(tmp_path, api) as client:
        client.post("/api/admin/spotify/player/next", headers=HEADERS)
        client.put(
            "/api/admin/spotify",
            headers=HEADERS,
            json={"max_volume": 50},
        )
        client.put("/api/admin/spotify/volume", headers=HEADERS, json={"volume": 90})
    assert "/player/next" in api.posts()
    volumes = [body for _, path, body in api.requests if path == "/player/volume"]
    # Saving max 50 turns the current 60 down, then 90 is capped to 50.
    assert volumes == [{"volume": 50}, {"volume": 50}]


def test_playlists_save_convert_and_play(tmp_path: Path) -> None:
    api = FakeApi(PLAYING_STATUS)
    with _client(tmp_path, api) as client:
        saved = client.put(
            "/api/admin/spotify/playlists",
            headers=HEADERS,
            json={
                "playlists": [
                    {
                        "name": " Warm-up ",
                        "uri": "https://open.spotify.com/playlist/37i9dQZF1DWUqIzZNMSCv3?si=x",
                    }
                ]
            },
        ).json()
        assert saved == [
            {"name": "Warm-up", "uri": "spotify:playlist:37i9dQZF1DWUqIzZNMSCv3"}
        ]
        listed = client.get("/api/admin/spotify/playlists", headers=HEADERS).json()
        assert listed == saved
        assert (
            client.post(
                "/api/admin/spotify/playlists/0/play", headers=HEADERS
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/admin/spotify/playlists/5/play", headers=HEADERS
            ).status_code
            == 404
        )
        bad = client.put(
            "/api/admin/spotify/playlists",
            headers=HEADERS,
            json={"playlists": [{"name": "x", "uri": "not a link"}]},
        )
        assert bad.status_code == 400
    assert (
        "POST",
        "/player/play",
        {"uri": "spotify:playlist:37i9dQZF1DWUqIzZNMSCv3"},
    ) in api.requests
