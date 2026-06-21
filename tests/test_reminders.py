"""Tests for reminder time calculation."""

from datetime import date, datetime, time

from raspberry_pab.models import Participant, ReminderRule
from raspberry_pab.reminders import (
    build_due_alerts,
    compute_fire_times,
    render_message,
)


def test_compute_single_offset_fire_time() -> None:
    rule = ReminderRule(
        id=1,
        offset_minutes=30,
        message_template="Warm Up {name}",
    )
    start_at = datetime(2026, 6, 21, 11, 0)
    assert compute_fire_times(start_at, rule) == [datetime(2026, 6, 21, 10, 30)]


def test_compute_repeating_fire_times_until_start() -> None:
    rule = ReminderRule(
        id=2,
        offset_minutes=15,
        message_template="Go to Start Line",
        repeat_every_minutes=5,
    )
    start_at = datetime(2026, 6, 21, 11, 0)
    assert compute_fire_times(start_at, rule) == [
        datetime(2026, 6, 21, 10, 45),
        datetime(2026, 6, 21, 10, 50),
        datetime(2026, 6, 21, 10, 55),
    ]


def test_render_message_substitutes_name() -> None:
    participant = Participant(
        id=1,
        name="Carlos",
        event_date=date(2026, 6, 21),
        start_time=time(11, 0),
    )
    assert render_message("Warm Up {name}", participant) == "Warm Up Carlos"


def test_build_due_alerts_returns_matching_fire_slot() -> None:
    participant = Participant(
        id=1,
        name="Carlos",
        event_date=date(2026, 6, 21),
        start_time=time(11, 0),
    )
    rule = ReminderRule(
        id=1,
        offset_minutes=30,
        message_template="Warm Up {name}",
    )
    alerts = build_due_alerts(
        [participant],
        [rule],
        datetime(2026, 6, 21, 10, 30),
    )
    assert len(alerts) == 1
    assert alerts[0].message == "Warm Up Carlos"
