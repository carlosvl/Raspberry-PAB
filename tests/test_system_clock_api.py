"""Tests for Pi system clock admin API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.server import create_app


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
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_get_system_clock(client: TestClient) -> None:
    payload = {
        "local_time": "2026-08-29T21:38:00",
        "timezone": "America/Chicago",
        "ntp": False,
        "ntp_raw": "no",
        "persists_offline": True,
        "fake_hwclock_saved": "2026-08-30 02:38:00",
    }
    with patch(
        "raspberry_pab.routes.system_clock._run_script",
        return_value=payload,
    ) as run_script:
        response = client.get(
            "/api/admin/system-clock",
            headers={"X-Admin-Pin": "9999"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["local_time"] == "2026-08-29T21:38:00"
    assert body["timezone"] == "America/Chicago"
    assert body["ntp"] is False
    assert body["simulated_kiosk"] is False
    assert body["persists_offline"] is True
    run_script.assert_called_once_with(["status", "--json"], use_sudo=False)


def test_set_system_clock(client: TestClient) -> None:
    payload = {
        "local_time": "2026-08-29T10:15:00",
        "timezone": "America/Chicago",
        "ntp": False,
        "ntp_raw": "no",
    }
    with patch(
        "raspberry_pab.routes.system_clock._run_script",
        return_value=payload,
    ) as run_script:
        response = client.put(
            "/api/admin/system-clock",
            headers={"X-Admin-Pin": "9999"},
            json={
                "year": 2026,
                "month": 8,
                "day": 29,
                "hour": 10,
                "minute": 15,
                "second": 0,
            },
        )
    assert response.status_code == 200
    assert response.json()["local_time"] == "2026-08-29T10:15:00"
    run_script.assert_called_once_with(["set", "2026-08-29 10:15:00"], use_sudo=True)


def test_set_system_clock_rejects_invalid_day(client: TestClient) -> None:
    response = client.put(
        "/api/admin/system-clock",
        headers={"X-Admin-Pin": "9999"},
        json={
            "year": 2026,
            "month": 2,
            "day": 31,
            "hour": 10,
            "minute": 0,
        },
    )
    assert response.status_code == 400


def test_system_clock_requires_pin(client: TestClient) -> None:
    response = client.get("/api/admin/system-clock")
    assert response.status_code == 401
