"""Tests for live MCA team standings formatting and API."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.race_results.mca_scoring import (
    DayStandings,
    ScoredRider,
    StandingsBucket,
    TeamScore,
    build_all_standings,
)
from raspberry_pab.race_results.team_standings_live import (
    abbreviate_team,
    buckets_from_standings,
    build_snapshot_from_standings,
    format_matrix_messages,
    format_ticker_text,
)
from raspberry_pab.server import create_app


def _score(
    *,
    team: str,
    points: int,
    level: str = "high_school",
    division: str = "D2",
) -> TeamScore:
    rider = ScoredRider(
        team_name=team,
        raw_name=f"{team} Rider",
        bib=None,
        place=1,
        points=points,
        category_label="Freshman Boys D2",
        race_date=date(2026, 9, 13),
        total_time="00:30:00",
        school_level=level,  # type: ignore[arg-type]
        gender="boy",
        field_division="D2" if division == "D2" else "D1",  # type: ignore[arg-type]
        results_url="https://example.test",
        results_status="official",
    )
    return TeamScore(
        team_name=team,
        school_level=level,  # type: ignore[arg-type]
        division=division,  # type: ignore[arg-type]
        total_points=points,
        gender_mix="B",
        scoring_riders=[rider],
        all_riders=[rider],
        division_inferred=True,
    )


def test_abbreviate_team() -> None:
    assert abbreviate_team("Roseville") == "Rosev"
    assert abbreviate_team("Austin HS").startswith("A")


def test_ticker_and_matrix_include_focus_and_top3() -> None:
    day = DayStandings(
        race_date=date(2026, 9, 13),
        buckets={
            StandingsBucket.HS_D1: [],
            StandingsBucket.HS_D2: [
                _score(team="Roseville", points=1899),
                _score(team="Austin HS", points=1837),
                _score(team="Chaska HS", points=1824),
                _score(team="Other", points=1000),
            ],
            StandingsBucket.MS_D1: [],
            StandingsBucket.MS_D2: [
                _score(
                    team="Roseville",
                    points=1869,
                    level="middle_school",
                ),
            ],
        },
    )
    buckets = buckets_from_standings([day], focus_team="Roseville")
    assert len(buckets) == 2
    hs = next(b for b in buckets if b.division_label == "HS D2")
    assert hs.focus_place == 1
    assert hs.focus_score == 1899
    assert [t.team_name for t in hs.top3] == [
        "Roseville",
        "Austin HS",
        "Chaska HS",
    ]

    ticker = format_ticker_text(buckets)
    assert "Roseville #1" in ticker
    assert "Austin HS 1837" in ticker
    assert "MS D2" in ticker

    messages = format_matrix_messages(buckets, focus_team="Roseville")
    assert messages
    assert all(len(msg) <= 36 for msg in messages)
    assert any("HS D2" in msg and "#1" in msg for msg in messages)

    snapshot = build_snapshot_from_standings(
        [day],
        series_url="https://example.test",
        focus_team="Roseville",
        scraped_at=datetime.now(UTC),
    )
    assert snapshot.ticker_text
    assert snapshot.matrix_messages


def test_team_standings_api_smoke(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        web_dir=Path(__file__).resolve().parents[1] / "web",
    )
    app = create_app(settings)
    # Inject an empty snapshot so GET works without network.
    day = DayStandings(
        race_date=date(2026, 9, 13),
        buckets={
            StandingsBucket.HS_D1: [],
            StandingsBucket.HS_D2: [_score(team="Roseville", points=500)],
            StandingsBucket.MS_D1: [],
            StandingsBucket.MS_D2: [],
        },
    )
    snapshot = build_snapshot_from_standings(
        [day],
        series_url="https://www.itsyourrace.com/results.aspx?id=17320",
        focus_team="Roseville",
        scraped_at=datetime.now(UTC),
    )
    app.state.team_standings_scheduler._snapshot = snapshot

    with TestClient(app) as client:
        response = client.get("/api/team-standings")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["focus_team"] == "Roseville"
        assert "Roseville #1" in data["ticker_text"]
        assert data["buckets"]

        config = client.get(
            "/api/admin/team-standings/config",
            headers={"X-Admin-Pin": "1234"},
        )
        assert config.status_code == 200
        assert config.json()["interval_minutes"] == 5

        updated = client.put(
            "/api/admin/team-standings/config",
            headers={"X-Admin-Pin": "1234"},
            json={
                "enabled": True,
                "series_url": "https://www.itsyourrace.com/results.aspx?id=17320",
                "focus_team": "Roseville",
                "interval_minutes": 10,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["interval_minutes"] == 10


def test_build_all_standings_still_works_with_live_helpers() -> None:
    riders = [
        ScoredRider(
            team_name="Roseville",
            raw_name="A",
            bib=None,
            place=1,
            points=500,
            category_label="Freshman Boys D2",
            race_date=date(2026, 9, 13),
            total_time=None,
            school_level="high_school",
            gender="boy",
            field_division="D2",
            results_url="https://example.test",
            results_status="official",
        )
    ]
    days = build_all_standings(riders)
    buckets = buckets_from_standings(days, focus_team="Roseville")
    assert buckets[0].focus_place == 1
