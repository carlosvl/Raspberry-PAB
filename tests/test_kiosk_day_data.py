"""Tests for loading a day's data when the simulated kiosk clock is set."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import (
    ParticipantCreate,
    ParticipantResultMatchRecord,
    RaceResultsSyncSummary,
)
from raspberry_pab.server import create_app
from raspberry_pab.test_scenarios import find_scenario_for_date, prepare_day_data

SATURDAY = date(2025, 8, 23)
SUNDAY = date(2025, 8, 24)


def _store(tmp_path: Path) -> ScheduleStore:
    store = ScheduleStore(tmp_path / "schedule.db")
    store.initialize()
    return store


def _summary(day: date, matched: int) -> RaceResultsSyncSummary:
    return RaceResultsSyncSummary(
        event_date=day, matched=matched, unmatched=0, ambiguous=0, sessions_synced=1
    )


def test_find_scenario_for_date() -> None:
    scenario = find_scenario_for_date(SATURDAY)
    assert scenario is not None
    assert scenario.id == "austin-2025-roseville"
    assert find_scenario_for_date(date(2031, 1, 1)) is None


def test_empty_day_seeds_only_that_date_and_syncs(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_participant(
        ParticipantCreate(name="Keep Me", event_date=SUNDAY, start_time=time(9, 0))
    )
    sync = MagicMock()
    sync.sync_date.return_value = _summary(SATURDAY, 8)

    data = prepare_day_data(store, SATURDAY, sync=sync)

    assert data.riders_before == 0
    assert data.riders_after == 8
    assert data.seeded_scenario_id == "austin-2025-roseville"
    assert data.results_sync is not None
    sync.sync_date.assert_called_once_with(SATURDAY)
    sunday = store.list_participants(SUNDAY)
    assert [p.name for p in sunday] == ["Keep Me"]


def test_existing_riders_are_not_reseeded(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_participant(
        ParticipantCreate(name="Solo", event_date=SATURDAY, start_time=time(9, 0))
    )
    sync = MagicMock()
    sync.sync_date.return_value = _summary(SATURDAY, 0)

    data = prepare_day_data(store, SATURDAY, sync=sync)

    assert data.seeded_scenario_id is None
    assert data.riders_after == 1
    sync.sync_date.assert_called_once_with(SATURDAY)


def test_riders_with_results_skip_seed_and_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    rider = store.create_participant(
        ParticipantCreate(name="Solo", event_date=SATURDAY, start_time=time(9, 0))
    )
    record = ParticipantResultMatchRecord(
        participant_id=rider.id,
        participant_name="Solo",
        event_date=SATURDAY,
        start_time=time(9, 0),
        place=3,
        match_method="exact",
        match_state="matched",
    )
    monkeypatch.setattr(store, "list_participant_result_matches", lambda _d: [record])
    sync = MagicMock()

    data = prepare_day_data(store, SATURDAY, sync=sync)

    assert data.results_present
    assert data.seeded_scenario_id is None
    sync.sync_date.assert_not_called()


def test_day_without_scenario_or_riders_loads_nothing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    sync = MagicMock()

    data = prepare_day_data(store, date(2031, 1, 1), sync=sync)

    assert data.riders_after == 0
    assert data.seeded_scenario_id is None
    sync.sync_date.assert_not_called()


def test_sync_failure_is_reported(tmp_path: Path) -> None:
    store = _store(tmp_path)
    sync = MagicMock()
    sync.sync_date.side_effect = OSError("network unreachable")

    data = prepare_day_data(store, SATURDAY, sync=sync)

    assert data.riders_after == 8
    assert data.results_error == "network unreachable"
    assert data.results_sync is None


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    web_dir = tmp_path / "web"
    (web_dir / "css").mkdir(parents=True)
    (web_dir / "js").mkdir()
    (web_dir / "index.html").write_text("<html></html>")
    (web_dir / "admin.html").write_text("<html></html>")
    (web_dir / "manifest.webmanifest").write_text("{}")
    (web_dir / "sw.js").write_text("")
    settings = Settings(data_dir=tmp_path / "data", web_dir=web_dir, admin_pin="9999")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_put_kiosk_clock_returns_day_data(client: TestClient) -> None:
    fake_sync = MagicMock()
    fake_sync.sync_date.side_effect = OSError("offline")
    with patch(
        "raspberry_pab.routes.kiosk_clock.RaceResultsSync",
        return_value=fake_sync,
    ):
        response = client.put(
            "/api/admin/kiosk-clock",
            headers={"X-Admin-Pin": "9999"},
            json={"simulated_now": "2025-08-23T10:25:00", "running": False},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["display_date"] == "2025-08-23"
    assert body["day_data"]["seeded_scenario_id"] == "austin-2025-roseville"
    assert body["day_data"]["riders_after"] == 8
    assert body["day_data"]["results_error"] == "offline"
    fake_sync.close.assert_called_once()

    state = client.get("/api/admin/kiosk-clock", headers={"X-Admin-Pin": "9999"})
    assert state.json()["day_data"] is None
