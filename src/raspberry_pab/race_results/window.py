"""Race-results auto-sync time window helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from raspberry_pab.db import ScheduleStore
from raspberry_pab.reminders import participant_start_at

RESULTS_SYNC_INTERVAL_KEY = "results_sync_interval_minutes"
RESULTS_SYNC_WINDOW_HOURS_KEY = "results_sync_window_hours"
DEFAULT_RESULTS_SYNC_MINUTES = 5
DEFAULT_RESULTS_SYNC_WINDOW_HOURS = 3


@dataclass(frozen=True)
class ResultsSyncWindow:
    active: bool
    window_start: datetime | None
    window_end: datetime | None
    next_eligible: datetime | None


def read_interval_minutes(store: ScheduleStore) -> int:
    raw = store.get_setting(RESULTS_SYNC_INTERVAL_KEY)
    if raw is not None:
        try:
            value = int(raw)
            if value >= 0:
                return value
        except ValueError:
            pass
    return DEFAULT_RESULTS_SYNC_MINUTES


def read_window_hours(store: ScheduleStore) -> int:
    raw = store.get_setting(RESULTS_SYNC_WINDOW_HOURS_KEY)
    if raw is not None:
        try:
            value = int(raw)
            if value >= 1:
                return value
        except ValueError:
            pass
    return DEFAULT_RESULTS_SYNC_WINDOW_HOURS


def results_sync_window(
    store: ScheduleStore,
    now: datetime,
    *,
    window_hours: int | None = None,
) -> ResultsSyncWindow:
    """Return whether auto-sync should run for today's schedule at ``now``.

    Active when earliest start <= now <= latest start + window_hours.
    """
    hours = window_hours if window_hours is not None else read_window_hours(store)
    participants = store.list_participants(now.date())
    if not participants:
        return ResultsSyncWindow(
            active=False,
            window_start=None,
            window_end=None,
            next_eligible=None,
        )

    starts = [
        participant_start_at(participant.event_date, participant.start_time)
        for participant in participants
    ]
    window_start = min(starts)
    window_end = max(starts) + timedelta(hours=hours)

    if now < window_start:
        return ResultsSyncWindow(
            active=False,
            window_start=window_start,
            window_end=window_end,
            next_eligible=window_start,
        )
    if now > window_end:
        return ResultsSyncWindow(
            active=False,
            window_start=window_start,
            window_end=window_end,
            next_eligible=None,
        )
    return ResultsSyncWindow(
        active=True,
        window_start=window_start,
        window_end=window_end,
        next_eligible=now,
    )
