"""API tests for schedule management and alert broadcasting."""

from datetime import datetime
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.scheduler import ReminderScheduler
from raspberry_pab.server import create_app


def make_web_dir(tmp_path: Path) -> Path:
    root = tmp_path / "web"
    (root / "css").mkdir(parents=True)
    (root / "js").mkdir()
    (root / "index.html").write_text("<html><body>Kiosk</body></html>")
    (root / "admin.html").write_text("<html><body>Admin</body></html>")
    return root


def test_admin_pin_required_for_writes(tmp_path: Path) -> None:
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/participants",
            json={
                "name": "Carlos",
                "event_date": "2026-06-21",
                "start_time": "11:00",
            },
        )
    assert response.status_code == 401


def test_participants_endpoint_returns_countdown(tmp_path: Path) -> None:
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
    )
    with TestClient(create_app(settings)) as client:
        created = client.post(
            "/api/participants",
            headers={"X-Admin-Pin": "9999"},
            json={
                "name": "Carlos",
                "event_date": "2026-06-21",
                "start_time": "11:00",
            },
        )
        response = client.get("/api/participants?date=2026-06-21")

    assert created.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["name"] == "Carlos"
    assert payload[0]["start_time"] == "11:00:00"
    assert "countdown_seconds" in payload[0]


def test_scheduler_publishes_active_alert(tmp_path: Path) -> None:
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
    )
    with TestClient(create_app(settings)) as client:
        client.post(
            "/api/participants",
            headers={"X-Admin-Pin": "9999"},
            json={
                "name": "Carlos",
                "event_date": "2026-06-21",
                "start_time": "11:00",
            },
        )
        scheduler = cast(ReminderScheduler, client.app.state.reminder_scheduler)
        client.portal.call(scheduler.tick, datetime(2026, 6, 21, 10, 30))
        response = client.get("/api/alerts/active")

    assert response.status_code == 200
    assert response.json()["message"] == "Warm Up Carlos"
