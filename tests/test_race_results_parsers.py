from __future__ import annotations

from datetime import date
from pathlib import Path

from raspberry_pab.race_results.itsyourrace import (
    parse_category_options,
    parse_results_page_html,
)
from raspberry_pab.race_results.precision_race import parse_precision_race_mca_html
from tests.race_results_helpers import load_fixture


def test_parse_precision_race_mca_index() -> None:
    html = load_fixture("precision_race_mca.html")
    events = parse_precision_race_mca_html(html, source_url="https://www.precisionrace.com/mca")
    pine_valley = next(
        event for event in events if event.iyr_series_id == "16915"
    )
    assert pine_valley.season_year == 2025
    assert pine_valley.race_number == "8"
    assert "Pine Valley" in pine_valley.venue_label
    assert pine_valley.date_saturday == date(2025, 10, 4)
    assert pine_valley.date_sunday == date(2025, 10, 5)


def test_parse_iyr_category_options() -> None:
    html = load_fixture("iyr_pine_valley_default.html")
    options = parse_category_options(html)
    labels = {option.label for option in options}
    assert "Freshman Boys D2" in labels
    assert any(option.eid == "137184" for option in options)


def test_parse_iyr_results_page_finds_carlos() -> None:
    html = load_fixture("iyr_pine_valley_freshman_boys_d2.html")
    session = parse_results_page_html(
        html,
        results_url="https://www.itsyourrace.com/Results.aspx?id=16915&y=2025&eid=137184",
        series_id="16915",
        season_year=2025,
        eid="137184",
    )
    assert session.category_label == "Freshman Boys D2"
    assert session.race_date == date(2025, 10, 5)
    carlos = next(
        row for row in session.rows if "Villalpando" in row.raw_name
    )
    assert carlos.place == 15
    assert carlos.bib == "3766"
    assert carlos.team_name == "Roseville"
    assert carlos.total_time == "00:39:54.300"
