"""The buzzer is gone: old databases and exports work, the matrix keeps its port."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from raspberry_pab.arduino_serial import effective_matrix_port
from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import ReminderRuleCreate, ReminderRuleUpdate
from raspberry_pab.server import create_app

LEGACY_COLUMNS = (
    ("buzzer_enabled", "INTEGER NOT NULL DEFAULT 0"),
    ("buzzer_pitch_hz", "INTEGER NOT NULL DEFAULT 2500"),
    ("buzzer_volume", "INTEGER NOT NULL DEFAULT 80"),
    ("buzzer_count", "INTEGER NOT NULL DEFAULT 3"),
    ("buzzer_beep_ms", "INTEGER NOT NULL DEFAULT 200"),
    ("buzzer_gap_ms", "INTEGER NOT NULL DEFAULT 150"),
)


def test_matrix_port_no_longer_falls_back_to_a_buzzer_port() -> None:
    assert effective_matrix_port(Settings(matrix_port="/dev/ttyUSB1")) == "/dev/ttyUSB1"
    assert effective_matrix_port(Settings()) == ""


def test_database_that_still_has_buzzer_columns_keeps_working(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy.db"
    store = ScheduleStore(db_path)
    store.initialize()
    with sqlite3.connect(db_path) as conn:
        for name, spec in LEGACY_COLUMNS:
            conn.execute(f"ALTER TABLE reminder_rules ADD COLUMN {name} {spec}")
        conn.execute(
            "INSERT INTO reminder_rules (offset_minutes, message_template, "
            "buzzer_enabled, buzzer_count) VALUES (30, 'Old {name}', 1, 7)"
        )
    store.initialize()  # re-running migrations must not choke on the old columns

    old = next(r for r in store.list_rules() if r.message_template == "Old {name}")
    assert not hasattr(old, "buzzer_enabled")

    created = store.create_rule(
        ReminderRuleCreate(offset_minutes=10, message_template="New {name}")
    )
    updated = store.update_rule(
        created.id, ReminderRuleUpdate(message_template="Newer {name}")
    )
    assert updated is not None
    assert updated.message_template == "Newer {name}"


def test_fresh_database_has_no_buzzer_columns(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "fresh.db")
    store.initialize()
    store.create_rule(ReminderRuleCreate(offset_minutes=5, message_template="Hi"))
    with sqlite3.connect(tmp_path / "fresh.db") as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(reminder_rules)")}
    assert not any(name.startswith("buzzer") for name in columns)


def test_buzzer_api_gone_and_old_import_still_accepted(tmp_path: Path) -> None:
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (web_dir / "admin.html").write_text("<html></html>", encoding="utf-8")
    settings = Settings(data_dir=tmp_path / "data", web_dir=web_dir, admin_pin="9999")
    headers = {"X-Admin-Pin": "9999"}
    with TestClient(create_app(settings)) as client:
        gone = client.post("/api/admin/buzzer/test", headers=headers, json={})
        assert gone.status_code == 404
        hardware = client.get("/api/admin/hardware-status", headers=headers).json()
        assert not any(key.startswith("buzzer") for key in hardware)
        imported = client.post(
            "/api/import",
            headers=headers,
            json={
                "event_date": "2026-10-03",
                "participants": [],
                "reminder_rules": [
                    {
                        "offset_minutes": 30,
                        "message_template": "Warm Up {name}",
                        "buzzer_enabled": True,
                        "buzzer_pitch_hz": 3000,
                    }
                ],
            },
        )
        assert imported.status_code == 200
        rules = client.get("/api/reminder-rules").json()
        assert [r["message_template"] for r in rules] == ["Warm Up {name}"]
        assert not any(key.startswith("buzzer") for key in rules[0])
