"""Tests for race-results sync-config admin API."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import ParticipantCreate
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
    store = ScheduleStore(settings.db_path)
    store.initialize()
    store.create_participant(
        ParticipantCreate(
            name="Nora",
            event_date=date.today(),
            start_time=time(12, 0),
            race="6th Girls",
        )
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_sync_config_defaults_and_update(client: TestClient) -> None:
    response = client.get(
        "/api/admin/race-results/sync-config",
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["interval_minutes"] == 5
    assert body["window_hours"] == 3
    assert "active" in body
    assert "kiosk_now" in body

    updated = client.put(
        "/api/admin/race-results/sync-config",
        headers={"X-Admin-Pin": "9999"},
        json={"interval_minutes": 5, "window_hours": 4},
    )
    assert updated.status_code == 200
    assert updated.json()["window_hours"] == 4

    legacy = client.put(
        "/api/admin/race-results/sync-interval",
        headers={"X-Admin-Pin": "9999"},
        json={"interval_minutes": 0},
    )
    assert legacy.status_code == 200
    assert legacy.json()["interval_minutes"] == 0
