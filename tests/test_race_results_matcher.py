from __future__ import annotations

from datetime import date, time

from raspberry_pab.models import Participant
from raspberry_pab.race_results.itsyourrace import parse_results_page_html
from raspberry_pab.race_results.matcher import (
    find_race_events_for_date,
    match_participant_in_sessions,
    names_match,
)
from raspberry_pab.race_results.precision_race import parse_precision_race_mca_html
from tests.race_results_helpers import load_fixture


def test_names_match_handles_middle_name() -> None:
    assert names_match("Carlos Mateo Villalpando", "Carlos Mateo Villalpando")
    assert names_match("Carlos Villalpando", "Carlos Mateo Villalpando")


def test_find_race_event_for_pine_valley_sunday() -> None:
    html = load_fixture("precision_race_mca.html")
    events = parse_precision_race_mca_html(html, source_url="https://www.precisionrace.com/mca")
    candidates = find_race_events_for_date(events, date(2025, 10, 5))
    assert len(candidates) == 1
    assert candidates[0].event.iyr_series_id == "16915"


def test_match_participant_in_freshman_results() -> None:
    html = load_fixture("iyr_pine_valley_freshman_boys_d2.html")
    session = parse_results_page_html(
        html,
        results_url="https://www.itsyourrace.com/Results.aspx?id=16915&y=2025&eid=137184",
        series_id="16915",
        season_year=2025,
        eid="137184",
    )
    events = parse_precision_race_mca_html(
        load_fixture("precision_race_mca.html"),
        source_url="https://www.precisionrace.com/mca",
    )
    race_event = next(event for event in events if event.iyr_series_id == "16915")
    participant = Participant(
        id=1,
        name="Carlos Mateo Villalpando",
        event_date=date(2025, 10, 5),
        start_time=time(12, 30),
    )
    matches = match_participant_in_sessions(participant, race_event, [session])
    assert len(matches) == 1
    assert matches[0].row.place == 15
