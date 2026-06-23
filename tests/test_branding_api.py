"""Tests for kiosk branding API."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.server import create_app

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n"
    b"\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    web_dir = tmp_path / "web"
    (web_dir / "css").mkdir(parents=True)
    (web_dir / "js").mkdir()
    (web_dir / "index.html").write_text("<html></html>")
    (web_dir / "admin.html").write_text("<html></html>")
    (web_dir / "manifest.webmanifest").write_text("{}")
    (web_dir / "sw.js").write_text("")
    settings = Settings(data_dir=tmp_path / "data", web_dir=web_dir, admin_pin="9999")
    return TestClient(create_app(settings))


def test_public_config_uses_saved_title(client: TestClient) -> None:
    response = client.put(
        "/api/admin/branding",
        json={"display_title": "Race Day"},
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 200

    config = client.get("/api/config").json()
    assert config["display_title"] == "Race Day"
    assert config["logo_url"] is None


def test_upload_and_serve_logo(client: TestClient) -> None:
    response = client.post(
        "/api/admin/branding/logo",
        files={"file": ("logo.png", BytesIO(PNG_BYTES), "image/png")},
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["has_logo"] is True
    assert payload["logo_url"].startswith("/api/branding/logo?v=")

    config = client.get("/api/config").json()
    assert config["logo_url"] is not None

    logo = client.get(config["logo_url"])
    assert logo.status_code == 200
    assert logo.headers["content-type"].startswith("image/png")
    assert logo.content == PNG_BYTES


def test_upload_rejects_non_png(client: TestClient) -> None:
    response = client.post(
        "/api/admin/branding/logo",
        files={"file": ("logo.jpg", BytesIO(b"not-a-png"), "image/jpeg")},
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 400


def test_delete_logo(client: TestClient) -> None:
    client.post(
        "/api/admin/branding/logo",
        files={"file": ("logo.png", BytesIO(PNG_BYTES), "image/png")},
        headers={"X-Admin-Pin": "9999"},
    )
    response = client.delete(
        "/api/admin/branding/logo",
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 204
    assert client.get("/api/config").json()["logo_url"] is None


def test_branding_requires_pin(client: TestClient) -> None:
    response = client.put("/api/admin/branding", json={"display_title": "Nope"})
    assert response.status_code == 401
