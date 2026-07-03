from __future__ import annotations

from datetime import date, time
from pathlib import Path

from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import ParticipantCreate
from raspberry_pab.race_results.sync import RaceResultsSync
from tests.race_results_helpers import load_fixture, make_fetch_text


def test_sync_index_and_match_carlos(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedule.db")
    store.initialize()
    sync = RaceResultsSync(store, fetch_text=make_fetch_text())
    try:
        events = sync.sync_index()
        assert any(event.iyr_series_id == "16915" for event in events)
        store.create_participant(
            ParticipantCreate(
                name="Carlos Mateo Villalpando",
                event_date=date(2025, 10, 5),
                start_time=time(12, 30),
            )
        )
        summary = sync.sync_date(date(2025, 10, 5))
        assert summary.matched == 1
        matches = sync.list_matches(date(2025, 10, 5))
        assert matches[0].place == 15
        assert matches[0].total_time == "00:39:54.300"
        assert matches[0].category_label == "Freshman Boys D2"
    finally:
        sync.close()
