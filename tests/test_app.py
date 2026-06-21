"""Tests for the Raspberry-PAB kiosk application."""

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
    (root / "css" / "kiosk.css").write_text("body { margin: 0; }")
    (root / "js" / "kiosk.js").write_text("console.log('kiosk');")
    return root


@pytest.fixture
def settings(tmp_path: Path, web_dir: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", web_dir=web_dir)


def test_settings_from_env(monkeypatch, tmp_path: Path, web_dir: Path) -> None:
    monkeypatch.setenv("PAB_DATA_DIR", str(tmp_path / "custom"))
    monkeypatch.setenv("PAB_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("PAB_PORT", "9090")
    monkeypatch.setenv("PAB_WEB_DIR", str(web_dir))
    settings = Settings.from_env()
    assert settings.data_dir == tmp_path / "custom"
    assert settings.log_level == "DEBUG"
    assert settings.port == 9090
    assert settings.web_dir == web_dir


def test_kiosk_url(settings: Settings) -> None:
    assert settings.kiosk_url == "http://127.0.0.1:8080"


def test_health_endpoint(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": settings.app_name}


def test_index_served(settings: Settings) -> None:
    client = TestClient(create_app(settings))
    response = client.get("/")
    assert response.status_code == 200
    assert "Kiosk" in response.text


def test_application_run_fails_without_web_dir(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", web_dir=tmp_path / "missing")
    app = Application(settings=settings)
    assert app.run() == 1
