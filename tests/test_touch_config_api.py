"""Tests for touch trackpad admin API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.server import create_app
from raspberry_pab import touch_config


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    web_dir = tmp_path / "web"
    (web_dir / "css").mkdir(parents=True)
    (web_dir / "js").mkdir()
    (web_dir / "index.html").write_text("<html></html>")
    (web_dir / "admin.html").write_text("<html></html>")
    (web_dir / "manifest.webmanifest").write_text("{}")
    (web_dir / "sw.js").write_text("")

    config_path = tmp_path / "touch-map.conf"
    monkeypatch.setattr(touch_config, "touch_config_path", lambda: config_path)

    settings = Settings(data_dir=tmp_path / "data", web_dir=web_dir, admin_pin="9999")
    return TestClient(create_app(settings))


def test_get_touch_config_defaults(client: TestClient) -> None:
    response = client.get("/api/admin/touch", headers={"X-Admin-Pin": "9999"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["tap_slop"] == 8
    assert payload["drag_start"] == 12
    assert payload["multi_tap_seconds"] == 0.45
    assert payload["sensitivity"] == 0.5


def test_update_touch_config_writes_file_and_restarts(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "touch-map.conf"
    calls: list[list[str]] = []

    def fake_popen(command: list[str], *, start_new_session: bool) -> object:
        calls.append(command)
        assert start_new_session
        return type("Process", (), {"pid": 1234})()

    setup_script = tmp_path / "setup-touch-input.sh"
    setup_script.write_text("#!/bin/bash\n", encoding="utf-8")
    setup_script.chmod(0o755)
    monkeypatch.setattr("raspberry_pab.routes.touch._setup_script", lambda: setup_script)
    monkeypatch.setattr("raspberry_pab.routes.touch.subprocess.Popen", fake_popen)

    response = client.put(
        "/api/admin/touch",
        json={
            "tap_slop": 12,
            "drag_start": 18,
            "multi_tap_seconds": 0.55,
            "sensitivity": 0.4,
        },
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 200
    assert response.json()["tap_slop"] == 12
    assert config_path.is_file()
    saved = config_path.read_text(encoding="utf-8")
    assert "PAB_TOUCH_TAP_SLOP=12" in saved
    assert "PAB_TOUCH_DRAG_START=18" in saved
    assert calls == [["bash", str(setup_script)]]


def test_update_touch_config_rejects_invalid_drag_start(client: TestClient) -> None:
    response = client.put(
        "/api/admin/touch",
        json={
            "tap_slop": 20,
            "drag_start": 10,
            "multi_tap_seconds": 0.45,
            "sensitivity": 0.5,
        },
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 400


def test_touch_config_requires_pin(client: TestClient) -> None:
    response = client.get("/api/admin/touch")
    assert response.status_code == 401
