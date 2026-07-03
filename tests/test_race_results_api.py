from __future__ import annotations

from datetime import date, time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from raspberry_pab.server import create_app
from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import ParticipantCreate
from raspberry_pab.race_results.sync import RaceResultsSync
from tests.race_results_helpers import make_fetch_text


def test_race_results_api(tmp_path: Path) -> None:
    db_path = tmp_path / "schedule.db"
    settings = Settings(data_dir=tmp_path, admin_pin="1234")
    app = create_app(settings)
    store = ScheduleStore(db_path)
    store.initialize()
    store.create_participant(
        ParticipantCreate(
            name="Carlos Mateo Villalpando",
            event_date=date(2025, 10, 5),
            start_time=time(12, 30),
        )
    )
    sync = RaceResultsSync(store, fetch_text=make_fetch_text())
    sync.sync_index()
    sync.sync_date(date(2025, 10, 5))
    sync.close()

    client = TestClient(app)
    response = client.get("/api/race-results?date=2025-10-05")
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["place"] == 15
    assert payload[0]["match_state"] == "matched"

    admin_headers = {"X-Admin-Pin": "1234"}
    index_response = client.post(
        "/api/admin/race-results/sync-index",
        headers=admin_headers,
    )
    assert index_response.status_code == 200
    assert len(index_response.json()) > 0

    participants = client.get("/api/participants?date=2025-10-05")
    assert participants.status_code == 200
    with patch(
        "raspberry_pab.routes.schedule.show_participant_on_board",
        return_value=True,
    ):
        visible = client.get("/api/participants?date=2025-10-05")
    assert visible.json()[0]["finish_place"] == 15
