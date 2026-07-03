"""Tests for predefined test scenarios."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

from unittest.mock import MagicMock

from raspberry_pab.db import ScheduleStore
from raspberry_pab.kiosk_clock import effective_now, is_simulated
from raspberry_pab.models import RaceResultsSyncSummary
from raspberry_pab.test_scenarios import (
    TestScenarioRunner,
    list_scenarios,
    load_scenario,
    seed_scenario_participants,
)
from tests.race_results_helpers import make_austin_fetch_text


def test_list_scenarios_includes_austin() -> None:
    scenarios = list_scenarios()
    assert any(item.id == "austin-2025-roseville" for item in scenarios)


def test_seed_austin_roster_staggered_times(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedule.db")
    store.initialize()
    scenario = load_scenario("austin-2025-roseville")
    count = seed_scenario_participants(store, scenario)
    assert count == 19
    saturday = store.list_participants(date(2025, 8, 23))
    sunday = store.list_participants(date(2025, 8, 24))
    assert len(saturday) == 8
    assert len(sunday) == 11
    assert saturday[0].start_time == time(10, 30)
    assert saturday[1].start_time == time(10, 45)
    assert sunday[0].start_time == time(10, 30)


def test_run_austin_scenario_seeds_sync_and_sets_clock(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedule.db")
    store.initialize()
    mock_sync = MagicMock()
    mock_sync.sync_index.return_value = []
    mock_sync.sync_date.side_effect = [
        RaceResultsSyncSummary(
            event_date=date(2025, 8, 23),
            matched=8,
            unmatched=0,
            ambiguous=0,
            sessions_synced=5,
        ),
        RaceResultsSyncSummary(
            event_date=date(2025, 8, 24),
            matched=11,
            unmatched=0,
            ambiguous=0,
            sessions_synced=6,
        ),
    ]
    runner = TestScenarioRunner(store, sync=mock_sync)
    result = runner.run("austin-2025-roseville")
    assert result.participants_seeded == 19
    assert is_simulated(store)
    assert effective_now(store).date() == date(2025, 8, 24)


def test_run_austin_with_fixtures_matches_ryan(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedule.db")
    store.initialize()
    from raspberry_pab.race_results.sync import RaceResultsSync

    runner = TestScenarioRunner(store, sync=RaceResultsSync(store, fetch_text=make_austin_fetch_text()))
    try:
        result = runner.run("austin-2025-roseville")
        assert result.participants_seeded == 19
        assert result.saturday.matched >= 1
        ryan = next(
            row
            for row in runner._sync.list_matches(date(2025, 8, 23))
            if "Kokotovich" in row.participant_name
        )
        assert ryan.place == 2
    finally:
        runner.close()
