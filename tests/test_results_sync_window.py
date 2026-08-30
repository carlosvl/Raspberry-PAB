"""Tests for race-results auto-sync window math."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import ParticipantCreate
from raspberry_pab.race_results.window import (
    DEFAULT_RESULTS_SYNC_MINUTES,
    DEFAULT_RESULTS_SYNC_WINDOW_HOURS,
    read_interval_minutes,
    read_window_hours,
    results_sync_window,
)


def _store_with_starts(tmp_path: Path, starts: list[time]) -> ScheduleStore:
    store = ScheduleStore(tmp_path / "schedule.db")
    store.initialize()
    event_date = date(2026, 8, 29)
    for index, start in enumerate(starts):
        store.create_participant(
            ParticipantCreate(
                name=f"Rider {index}",
                event_date=event_date,
                start_time=start,
                race="Test",
            )
        )
    return store


def test_window_empty_day(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "empty.db")
    store.initialize()
    window = results_sync_window(store, datetime(2026, 8, 29, 12, 0), window_hours=3)
    assert window.active is False
    assert window.window_start is None
    assert window.next_eligible is None


def test_window_before_first_start(tmp_path: Path) -> None:
    store = _store_with_starts(tmp_path, [time(12, 0), time(14, 0)])
    window = results_sync_window(store, datetime(2026, 8, 29, 11, 0), window_hours=3)
    assert window.active is False
    assert window.window_start == datetime(2026, 8, 29, 12, 0)
    assert window.window_end == datetime(2026, 8, 29, 17, 0)
    assert window.next_eligible == datetime(2026, 8, 29, 12, 0)


def test_window_inside(tmp_path: Path) -> None:
    store = _store_with_starts(tmp_path, [time(12, 0), time(14, 0)])
    window = results_sync_window(store, datetime(2026, 8, 29, 13, 30), window_hours=3)
    assert window.active is True
    assert window.window_start == datetime(2026, 8, 29, 12, 0)
    assert window.window_end == datetime(2026, 8, 29, 17, 0)


def test_window_after_latest_plus_hours(tmp_path: Path) -> None:
    store = _store_with_starts(tmp_path, [time(12, 0), time(14, 0)])
    window = results_sync_window(store, datetime(2026, 8, 29, 17, 1), window_hours=3)
    assert window.active is False
    assert window.next_eligible is None


def test_defaults() -> None:
    assert DEFAULT_RESULTS_SYNC_MINUTES == 5
    assert DEFAULT_RESULTS_SYNC_WINDOW_HOURS == 3


def test_read_settings(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "settings.db")
    store.initialize()
    assert read_interval_minutes(store) == 5
    assert read_window_hours(store) == 3
    store.set_setting("results_sync_interval_minutes", "0")
    store.set_setting("results_sync_window_hours", "4")
    assert read_interval_minutes(store) == 0
    assert read_window_hours(store) == 4
