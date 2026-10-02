"""Tests for the Spotify Jam QR link: validation, QR output and the API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.server import create_app
from raspberry_pab.spotify_jam import normalize_jam_url, qr_svg

HEADERS = {"X-Admin-Pin": "9999"}
JAM = "https://spotify.link/AbCdEf123?si=xyz"


def _client(tmp_path: Path) -> TestClient:
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (web_dir / "admin.html").write_text("<html></html>", encoding="utf-8")
    settings = Settings(data_dir=tmp_path / "data", web_dir=web_dir, admin_pin="9999")
    return TestClient(create_app(settings))


@pytest.mark.parametrize(
    "url",
    [
        JAM,
        "https://open.spotify.com/socialsession/abc123?si=1",
        "https://spotify.app.link/xyz",
        "  https://open.spotify.com/jam/abc  ",
    ],
)
def test_normalize_accepts_spotify_links(url: str) -> None:
    assert normalize_jam_url(url) == url.strip()


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://spotify.link/abc",
        "https://evil.example/spotify.com",
        "https://spotify.com.evil.example/x",
        "https://notspotify.link/x",
        "javascript:alert(1)",
        "spotify:playlist:37i9dQZF1DWUqIzZNMSCv3",
        "https://open.spotify.com/" + "a" * 600,
    ],
)
def test_normalize_rejects_other_links(url: str) -> None:
    with pytest.raises(ValueError):
        normalize_jam_url(url)


def test_qr_svg_is_inline_svg() -> None:
    svg = qr_svg(JAM)
    assert svg.startswith("<svg")
    assert "<?xml" not in svg
    assert "viewBox=" in svg
    assert "width=" not in svg


def test_jam_api_round_trip(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        _round_trip(client)


def _round_trip(client: TestClient) -> None:
    assert client.get("/api/spotify/jam").json() == {
        "active": False,
        "url": None,
        "svg": None,
    }

    assert client.put("/api/admin/spotify/jam", json={"url": JAM}).status_code == 401
    shown = client.put("/api/admin/spotify/jam", headers=HEADERS, json={"url": JAM})
    assert shown.status_code == 200

    public = client.get("/api/spotify/jam").json()  # no PIN: the kiosk reads this
    assert public["active"] is True
    assert public["url"] == JAM
    assert public["svg"].startswith("<svg")
    assert client.get("/api/admin/spotify/jam", headers=HEADERS).json()["active"]

    assert client.delete("/api/admin/spotify/jam").status_code == 401
    cleared = client.delete("/api/admin/spotify/jam", headers=HEADERS)
    assert cleared.json()["active"] is False
    assert client.get("/api/spotify/jam").json()["active"] is False


def test_jam_api_rejects_bad_link(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        bad = client.put(
            "/api/admin/spotify/jam",
            headers=HEADERS,
            json={"url": "https://evil.example/x"},
        )
        assert bad.status_code == 400
        assert client.get("/api/spotify/jam").json()["active"] is False
