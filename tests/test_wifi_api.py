"""API tests for local admin Wi-Fi management."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.server import create_app


def make_web_dir(tmp_path: Path) -> Path:
    root = tmp_path / "web"
    (root / "css").mkdir(parents=True)
    (root / "js").mkdir()
    (root / "index.html").write_text("<html><body>Kiosk</body></html>")
    (root / "admin.html").write_text("<html><body>Admin</body></html>")
    return root


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    script = tmp_path / "manage-pi-wifi.sh"
    script.write_text("#!/bin/bash\n")
    script.chmod(0o755)
    monkeypatch.setattr(
        "raspberry_pab.routes.wifi._manage_script",
        lambda: script,
    )
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
    )
    return TestClient(create_app(settings))


def test_wifi_status_requires_admin_pin(app_client: TestClient) -> None:
    response = app_client.get("/api/admin/wifi/status")
    assert response.status_code == 401


def test_wifi_status_requires_local_client(
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny(_request: object) -> None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wi-Fi controls are only available on the local kiosk display",
        )

    monkeypatch.setattr("raspberry_pab.routes.wifi._require_local_client", deny)
    response = app_client.get(
        "/api/admin/wifi/status",
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 403


def test_wifi_status_ok(
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "iface": "wlan0",
        "connection": "QualitySuites",
        "ssid": "QualitySuites",
        "ipv4": "172.17.1.10",
        "on_hotspot": False,
        "state": "100 (connected)",
        "hotspot_connection": "PAB-Hotspot",
    }

    def fake_run(*_args: str, timeout: float = 30.0) -> dict:
        assert timeout > 0
        return payload

    monkeypatch.setattr("raspberry_pab.routes.wifi._run_manage", fake_run)
    response = app_client.get(
        "/api/admin/wifi/status",
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 200
    assert response.json() == payload


def test_wifi_scan_ok(
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "networks": [
            {
                "ssid": "QualitySuites",
                "signal": 80,
                "security": "WPA2",
                "in_use": False,
                "secured": True,
            }
        ]
    }
    monkeypatch.setattr(
        "raspberry_pab.routes.wifi._run_manage",
        lambda *a, timeout=30.0: payload,
    )
    response = app_client.post(
        "/api/admin/wifi/scan",
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 200
    assert response.json() == payload


def test_wifi_connect_ok(
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple] = []

    def fake_run(*args: str, timeout: float = 30.0) -> dict:
        calls.append((args, timeout))
        return {
            "ok": True,
            "ssid": "QualitySuites",
            "connection": "QualitySuites",
            "ipv4": "172.17.1.10",
            "message": "connected",
        }

    monkeypatch.setattr("raspberry_pab.routes.wifi._run_manage", fake_run)
    response = app_client.post(
        "/api/admin/wifi/connect",
        headers={"X-Admin-Pin": "9999"},
        json={"ssid": "QualitySuites", "password": "secret"},
    )
    assert response.status_code == 200
    assert response.json()["ssid"] == "QualitySuites"
    assert calls[0][0] == ("connect", "QualitySuites", "secret")


def test_wifi_forget_rejects_hotspot(app_client: TestClient) -> None:
    response = app_client.delete(
        "/api/admin/wifi/saved/PAB-Hotspot",
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 400
    assert "hotspot" in response.json()["detail"].lower()


def test_wifi_forget_ok(
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "raspberry_pab.routes.wifi._run_manage",
        lambda *a, timeout=30.0: {"ok": True, "forgotten": "OldNet"},
    )
    response = app_client.delete(
        "/api/admin/wifi/saved/OldNet",
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "forgotten": "OldNet"}


def test_wifi_script_failure_maps_to_502(
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = MagicMock()
    completed.returncode = 1
    completed.stderr = "Connection failed."
    completed.stdout = ""
    monkeypatch.setattr(
        "raspberry_pab.routes.wifi.subprocess.run",
        lambda *a, **k: completed,
    )
    response = app_client.post(
        "/api/admin/wifi/connect",
        headers={"X-Admin-Pin": "9999"},
        json={"ssid": "BadNet", "password": "x"},
    )
    assert response.status_code == 502
    assert "Connection failed" in response.json()["detail"]


def test_wifi_script_timeout_maps_to_504(
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess as sp

    def boom(*_a, **_k):
        raise sp.TimeoutExpired(cmd="manage", timeout=1)

    monkeypatch.setattr("raspberry_pab.routes.wifi.subprocess.run", boom)
    response = app_client.post(
        "/api/admin/wifi/scan",
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 504


def test_run_manage_parses_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from raspberry_pab.routes import wifi as wifi_routes

    script = tmp_path / "manage-pi-wifi.sh"
    script.write_text("#!/bin/bash\n")
    script.chmod(0o755)
    monkeypatch.setattr(wifi_routes, "_manage_script", lambda: script)

    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = json.dumps({"networks": []})
    completed.stderr = ""
    monkeypatch.setattr(wifi_routes.subprocess, "run", lambda *a, **k: completed)

    assert wifi_routes._run_manage("saved") == {"networks": []}
