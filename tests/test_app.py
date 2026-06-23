"""Tests for the Raspberry-PAB kiosk application."""

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raspberry_pab.app import Application
from raspberry_pab.config import Settings
from raspberry_pab.server import create_app


@pytest.fixture
def web_dir(tmp_path: Path) -> Path:
    root = tmp_path / "web"
    (root / "css").mkdir(parents=True)
    (root / "js").mkdir()
    (root / "index.html").write_text("<html><body>Kiosk</body></html>")
    (root / "admin.html").write_text("<html><body>Admin</body></html>")
    (root / "manifest.webmanifest").write_text("{}")
    (root / "sw.js").write_text("self.addEventListener('fetch', () => {});")
    (root / "css" / "kiosk.css").write_text("body { margin: 0; }")
    (root / "js" / "kiosk.js").write_text("console.log('kiosk');")
    return root


@pytest.fixture
def settings(tmp_path: Path, web_dir: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", web_dir=web_dir)


def test_settings_from_env(monkeypatch, tmp_path: Path, web_dir: Path) -> None:
    monkeypatch.setenv("PAB_DATA_DIR", str(tmp_path / "custom"))
    monkeypatch.setenv("PAB_DISPLAY_TITLE", "Start List")
    monkeypatch.setenv("PAB_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("PAB_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("PAB_PORT", "9090")
    monkeypatch.setenv("PAB_WEB_DIR", str(web_dir))
    settings = Settings.from_env()
    assert settings.data_dir == tmp_path / "custom"
    assert settings.display_title == "Start List"
    assert settings.log_level == "DEBUG"
    assert settings.bind_host == "0.0.0.0"
    assert settings.port == 9090
    assert settings.web_dir == web_dir


def test_kiosk_url(settings: Settings) -> None:
    assert settings.kiosk_url == "http://127.0.0.1:8080"


def test_health_endpoint(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": settings.app_name}


def test_public_config_endpoint(settings: Settings) -> None:
    settings = replace(settings, display_title="Start List")
    client = TestClient(create_app(settings))
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json() == {
        "app_name": "Raspberry-PAB",
        "display_title": "Start List",
        "logo_url": None,
        "port": 8080,
    }


def test_index_served(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.get("/")
    assert response.status_code == 200
    assert "Kiosk" in response.text


def test_pwa_files_served(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    manifest = client.get("/manifest.webmanifest")
    service_worker = client.get("/sw.js")
    assert manifest.status_code == 200
    assert manifest.headers["content-type"].startswith("application/manifest+json")
    assert service_worker.status_code == 200
    assert service_worker.headers["content-type"].startswith("text/javascript")


def test_network_endpoint(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.get("/api/network")
    assert response.status_code == 200
    payload = response.json()
    assert payload["port"] == 8080
    assert payload["mdns_name"].endswith(".local")
    assert payload["hotspot_url"] == "http://10.42.0.1:8080"
    assert isinstance(payload["urls"], list)


def test_application_run_uses_bind_host(monkeypatch, settings: Settings) -> None:
    calls: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> None:
        calls["host"] = kwargs["host"]
        calls["port"] = kwargs["port"]

    monkeypatch.setattr("raspberry_pab.app.uvicorn.run", fake_run)
    app = Application(settings=replace(settings, bind_host="0.0.0.0"))
    assert app.run() == 0
    assert calls == {"host": "0.0.0.0", "port": 8080}


def test_application_run_fails_without_web_dir(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", web_dir=tmp_path / "missing")
    app = Application(settings=settings)
    assert app.run() == 1
