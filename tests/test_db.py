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
            )
        ],
    )

    store.import_schedule(schedule)
    exported = store.export_schedule(date(2026, 6, 21))

    assert exported.event_date == schedule.event_date
    assert exported.participants == schedule.participants
    assert exported.reminder_rules == schedule.reminder_rules
