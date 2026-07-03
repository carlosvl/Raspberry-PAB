"""Simulated kiosk clock for race-day testing."""

from __future__ import annotations

import time
from datetime import datetime

from raspberry_pab.db import ScheduleStore

SIMULATED_NOW_KEY = "kiosk_simulated_now"
SIMULATED_RUNNING_KEY = "kiosk_simulated_running"
SIMULATED_STARTED_MONO_KEY = "kiosk_simulated_started_mono"


def effective_now(store: ScheduleStore) -> datetime:
    anchor_raw = store.get_setting(SIMULATED_NOW_KEY)
    if not anchor_raw:
        return datetime.now()
    anchor = datetime.fromisoformat(anchor_raw)
    running = store.get_setting(SIMULATED_RUNNING_KEY) == "true"
    if not running:
        return anchor
    started_mono_raw = store.get_setting(SIMULATED_STARTED_MONO_KEY)
    if not started_mono_raw:
        return anchor
    elapsed = time.monotonic() - float(started_mono_raw)
    return anchor + _seconds_to_timedelta(elapsed)


def is_simulated(store: ScheduleStore) -> bool:
    return store.get_setting(SIMULATED_NOW_KEY) is not None


def is_running(store: ScheduleStore) -> bool:
    return store.get_setting(SIMULATED_RUNNING_KEY) == "true"


def set_simulated_now(
    store: ScheduleStore,
    *,
    when: datetime,
    running: bool = True,
) -> datetime:
    store.set_setting(SIMULATED_NOW_KEY, when.isoformat(timespec="seconds"))
    store.set_setting(SIMULATED_RUNNING_KEY, "true" if running else "false")
    if running:
        store.set_setting(SIMULATED_STARTED_MONO_KEY, str(time.monotonic()))
    else:
        store.delete_setting(SIMULATED_STARTED_MONO_KEY)
    return when


def clear_simulated_clock(store: ScheduleStore) -> None:
    store.delete_setting(SIMULATED_NOW_KEY)
    store.delete_setting(SIMULATED_RUNNING_KEY)
    store.delete_setting(SIMULATED_STARTED_MONO_KEY)


def get_clock_state(store: ScheduleStore) -> dict[str, str | bool | None]:
    anchor_raw = store.get_setting(SIMULATED_NOW_KEY)
    now = effective_now(store)
    return {
        "simulated": is_simulated(store),
        "running": is_running(store),
        "anchor": anchor_raw,
        "kiosk_now": now.isoformat(timespec="seconds"),
        "display_date": now.date().isoformat(),
    }


def _seconds_to_timedelta(seconds: float):
    from datetime import timedelta

    return timedelta(seconds=seconds)
