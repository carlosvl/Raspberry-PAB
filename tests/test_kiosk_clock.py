"""Tests for simulated kiosk clock."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from raspberry_pab.db import ScheduleStore
from raspberry_pab.kiosk_clock import (
    clear_simulated_clock,
    effective_now,
    get_clock_state,
    is_simulated,
    set_simulated_now,
)


def test_simulated_clock_freezes_when_paused(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedule.db")
    store.initialize()
    anchor = datetime(2025, 8, 24, 10, 25, 0)
    set_simulated_now(store, when=anchor, running=False)
    assert effective_now(store) == anchor
    assert is_simulated(store)


def test_clear_simulated_clock_uses_real_time(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedule.db")
    store.initialize()
    set_simulated_now(store, when=datetime(2025, 8, 24, 10, 25, 0), running=False)
    clear_simulated_clock(store)
    assert not is_simulated(store)
    state = get_clock_state(store)
    assert state["simulated"] is False
