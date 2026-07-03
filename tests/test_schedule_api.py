"""API tests for schedule management and alert broadcasting."""

from datetime import datetime
from pathlib import Path
from typing import cast
from unittest.mock import patch

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


def test_admin_pin_verify_endpoint(tmp_path: Path) -> None:
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
    )
    with TestClient(create_app(settings)) as client:
        denied = client.get("/api/admin/verify", headers={"X-Admin-Pin": "1111"})
        allowed = client.get("/api/admin/verify", headers={"X-Admin-Pin": "9999"})

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json() == {"authenticated": True}


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
        with patch(
            "raspberry_pab.routes.schedule.effective_now",
            return_value=datetime(2026, 6, 21, 10, 0),
        ):
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


def test_reminder_rule_led_fields_round_trip(tmp_path: Path) -> None:
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
    )
    payload = {
        "offset_minutes": 20,
        "message_template": "LED Alert {name}",
        "repeat_every_minutes": None,
        "enabled": True,
        "sort_order": 0,
        "led_enabled": True,
        "led_red": 255,
        "led_green": 64,
        "led_blue": 32,
        "led_flash_interval_ms": 300,
        "led_flash_duration_seconds": 15,
    }
    with TestClient(create_app(settings)) as client:
        created = client.post(
            "/api/reminder-rules",
            headers={"X-Admin-Pin": "9999"},
            json=payload,
        )
        listed = client.get("/api/reminder-rules")

    assert created.status_code == 200
    body = created.json()
    assert body["led_enabled"] is True
    assert body["led_red"] == 255
    assert body["led_flash_interval_ms"] == 300
    assert listed.status_code == 200
    saved = next(rule for rule in listed.json() if rule["id"] == body["id"])
    assert saved["led_flash_duration_seconds"] == 15


def test_exit_browser_endpoint(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_popen(command: list[str], *, start_new_session: bool) -> object:
        calls.append(command)
        assert start_new_session
        return type("Process", (), {"pid": 1234})()

    monkeypatch.setattr("raspberry_pab.routes.kiosk.subprocess.Popen", fake_popen)
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
    )
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/kiosk/exit-browser")

    assert response.status_code == 200
    assert response.json() == {"closing": True}
    assert calls == [["sh", "-c", "pkill chromium || pkill chromium-browser || true"]]


def test_keyboard_endpoint_launches_script(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    keyboard_script = tmp_path / "touch-keyboard.sh"
    keyboard_script.write_text("#!/usr/bin/env sh\n")

    def fake_popen(command: list[str], *, start_new_session: bool) -> object:
        calls.append(command)
        assert start_new_session
        return type("Process", (), {"pid": 1234})()

    monkeypatch.setattr("raspberry_pab.routes.kiosk.subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        "raspberry_pab.routes.kiosk._keyboard_script",
        lambda: keyboard_script,
    )
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
    )
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/kiosk/keyboard")

    assert response.status_code == 200
    assert response.json() == {"opening": True}
    assert calls == [["bash", str(keyboard_script)]]


def test_restart_service_requires_admin_pin(tmp_path: Path) -> None:
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
    )
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/kiosk/restart-service")

    assert response.status_code == 401


def test_restart_service_launches_systemctl(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_popen(command: list[str], *, start_new_session: bool) -> object:
        calls.append(command)
        assert start_new_session
        return type("Process", (), {"pid": 1234})()

    monkeypatch.setattr("raspberry_pab.routes.kiosk.subprocess.Popen", fake_popen)
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/kiosk/restart-service",
            headers={"X-Admin-Pin": "9999"},
        )

    assert response.status_code == 200
    assert response.json() == {"restarting": True}
    assert calls == [["sudo", "-n", "systemctl", "restart", "raspberry-pab"]]
