"""Tests for SQLite schedule storage."""

from datetime import date, time
from pathlib import Path

from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import (
    ParticipantCreate,
    ReminderRuleCreate,
    ScheduleImport,
    ScheduleParticipantImport,
)


def test_participant_crud(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedule.db")
    store.initialize()
    participant = store.create_participant(
        ParticipantCreate(
            name="Carlos",
            event_date=date(2026, 6, 21),
            start_time=time(11, 0),
        )
    )

    participants = store.list_participants(date(2026, 6, 21))
    assert participants == [participant]

    assert store.delete_participant(participant.id)
    assert store.list_participants(date(2026, 6, 21)) == []


def test_import_export_round_trip(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedule.db")
    store.initialize()
    schedule = ScheduleImport(
        event_date=date(2026, 6, 21),
        participants=[
            ScheduleParticipantImport(name="Carlos", start_time=time(11, 0)),
        ],
        reminder_rules=[
            ReminderRuleCreate(
                offset_minutes=30,
                message_template="Warm Up {name}",
                led_enabled=True,
                led_red=255,
                led_green=128,
                led_blue=0,
                led_flash_interval_ms=250,
                led_flash_duration_seconds=8,
            )
        ],
    )

    store.import_schedule(schedule)
    exported = store.export_schedule(date(2026, 6, 21))

    assert exported.event_date == schedule.event_date
    assert exported.participants == schedule.participants
    assert exported.reminder_rules == schedule.reminder_rules


def test_rule_led_fields_persist(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedule.db")
    store.initialize()
    created = store.create_rule(
        ReminderRuleCreate(
            offset_minutes=10,
            message_template="LED Test {name}",
            led_enabled=True,
            led_red=10,
            led_green=20,
            led_blue=30,
            led_flash_interval_ms=400,
            led_flash_duration_seconds=12,
            led_chase_duration_seconds=6,
        )
    )
    loaded = store.get_rule(created.id)
    assert loaded == created
    assert loaded is not None
    assert loaded.led_chase_duration_seconds == 6


def test_rule_buzzer_fields_persist(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedule.db")
    store.initialize()
    created = store.create_rule(
        ReminderRuleCreate(
            offset_minutes=10,
            message_template="Buzzer {name}",
            buzzer_enabled=True,
            buzzer_pitch_hz=3000,
            buzzer_volume=60,
            buzzer_count=5,
            buzzer_beep_ms=250,
            buzzer_gap_ms=100,
        )
    )
    loaded = store.get_rule(created.id)
    assert loaded is not None
    assert loaded.buzzer_enabled is True
    assert loaded.buzzer_pitch_hz == 3000
    assert loaded.buzzer_count == 5
