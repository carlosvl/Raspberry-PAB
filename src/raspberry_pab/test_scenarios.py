"""Load and run predefined test scenarios."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

from raspberry_pab.db import ScheduleStore
from raspberry_pab.kiosk_clock import set_simulated_now
from raspberry_pab.models import (
    ParticipantCreate,
    RaceResultsSyncSummary,
    TestScenarioDefinition,
    TestScenarioRunResult,
    TestScenarioSummary,
)
from raspberry_pab.race_results.sync import RaceResultsSync

_SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "data" / "test_scenarios"


def scenarios_dir() -> Path:
    return _SCENARIOS_DIR


def list_scenarios() -> list[TestScenarioSummary]:
    summaries: list[TestScenarioSummary] = []
    if not _SCENARIOS_DIR.is_dir():
        return summaries
    for path in sorted(_SCENARIOS_DIR.glob("*.json")):
        scenario = load_scenario(path.stem)
        summaries.append(
            TestScenarioSummary(
                id=scenario.id,
                label=scenario.label,
                saturday=scenario.saturday,
                sunday=scenario.sunday,
                roster_count=len(scenario.roster),
            )
        )
    return summaries


def load_scenario(scenario_id: str) -> TestScenarioDefinition:
    path = _SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Unknown test scenario: {scenario_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return TestScenarioDefinition.model_validate(payload)


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _staggered_start(first_start: time, stagger_minutes: int, index: int) -> time:
    base = datetime.combine(date.min, first_start)
    shifted = base + timedelta(minutes=stagger_minutes * index)
    return shifted.time()


def seed_scenario_participants(
    store: ScheduleStore,
    scenario: TestScenarioDefinition,
) -> int:
    dates = {scenario.saturday, scenario.sunday}
    for event_date in dates:
        store.delete_participants_for_date(event_date)
    first_start = _parse_time(scenario.first_start_time)
    day_indexes = {"saturday": 0, "sunday": 0}
    created = 0
    for rider in scenario.roster:
        event_date = scenario.saturday if rider.day == "saturday" else scenario.sunday
        start_time = _staggered_start(
            first_start,
            scenario.stagger_minutes,
            day_indexes[rider.day],
        )
        day_indexes[rider.day] += 1
        store.create_participant(
            ParticipantCreate(
                name=rider.name,
                event_date=event_date,
                start_time=start_time,
            )
        )
        created += 1
    return created


class TestScenarioRunner:
    def __init__(
        self,
        store: ScheduleStore,
        *,
        sync: RaceResultsSync | None = None,
    ) -> None:
        self._store = store
        self._sync = sync or RaceResultsSync(store)
        self._owns_sync = sync is None

    def close(self) -> None:
        if self._owns_sync:
            self._sync.close()

    def run(self, scenario_id: str) -> TestScenarioRunResult:
        scenario = load_scenario(scenario_id)
        participants_seeded = seed_scenario_participants(self._store, scenario)
        self._sync.sync_index()
        saturday_summary = self._sync.sync_date(scenario.saturday)
        sunday_summary = self._sync.sync_date(scenario.sunday)
        simulated_now = set_simulated_now(
            self._store,
            when=scenario.default_simulated_now,
            running=True,
        )
        return TestScenarioRunResult(
            scenario_id=scenario.id,
            label=scenario.label,
            participants_seeded=participants_seeded,
            saturday=saturday_summary,
            sunday=sunday_summary,
            kiosk_date_suggested=scenario.sunday,
            simulated_now=simulated_now,
        )
