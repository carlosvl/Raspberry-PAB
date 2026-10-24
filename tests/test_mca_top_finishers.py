"""Tests for the top-finishers lists (race places and season standings)."""

from __future__ import annotations

from datetime import date
from urllib.parse import unquote_plus

from raspberry_pab.race_results.itsyourrace import ParsedIyrSession, ParsedResultRow
from raspberry_pab.race_results.state_qualification import RiderSeason, SeasonCell
from raspberry_pab.race_results.top_finishers import (
    bibs_from_sessions,
    category_key,
    display_name,
    locator_links,
    top_race,
    top_season,
)


def _row(place: int, name: str, bib: str, laps: int = 1) -> ParsedResultRow:
    time = "00:30:00.0" if laps else "00:00:00.0"
    return ParsedResultRow(place, name, bib, "Team A", laps, time, "3.75 miles")


def _session(label: str, rows: list[ParsedResultRow]) -> ParsedIyrSession:
    return ParsedIyrSession(
        "1", 2026, "e", label, date(2026, 10, 11), "Unofficial", "u", rows, 1
    )


def test_category_key_only_wanted_categories() -> None:
    assert category_key("Varsity Girls") is not None
    assert category_key("JV2 Boys D1") is not None
    assert category_key("Senior Open") is None
    assert category_key("8th Grade Boys D1") is None
    assert category_key("Varsity Girls") < category_key("Varsity Boys")  # type: ignore[operator]


def test_display_name_cleanup() -> None:
    assert display_name("rylan O''HEARN") == "Rylan O'Hearn"
    assert display_name("RIVDEN CUMMINGS") == "Rivden Cummings"
    assert display_name("Mary McDonald") == "Mary McDonald"


def test_locator_links_are_encoded() -> None:
    strava, search = locator_links("Jo O'Neil", "St Cloud")
    assert strava.startswith("https://www.strava.com/athletes/search?text=Jo+O%27Neil")
    assert unquote_plus(search.split("q=")[1]) == '"Jo O\'Neil" St Cloud mountain bike'


def test_top_race_drops_dnf_and_other_categories() -> None:
    sessions = [
        _session("Senior Open", [_row(1, "A", "1")]),
        _session(
            "JV3 Boys",
            [_row(1, "FIRST RIDER", "10"), _row(2, "Dnf Rider", "11", laps=0)]
            + [_row(n, f"Rider {n}", str(10 + n)) for n in range(3, 20)],
        ),
    ]
    lists = top_race(sessions, top=5)
    assert list(lists) == ["JV3 Boys"]
    rows = lists["JV3 Boys"]
    assert [f.rank for f in rows] == [1, 3, 4, 5, 6]
    assert rows[0].name == "First Rider"
    assert rows[0].bib == "10"


def _rider(plate: str, name: str, points: list[int]) -> RiderSeason:
    cells = [SeasonCell(str(i), "race", p) for i, p in enumerate(points, start=1)]
    return RiderSeason(plate, name, "Team A", "Varsity Boys", cells)


def test_top_season_ties_share_rank_and_bib_fallback() -> None:
    riders = [
        _rider("a|team a", "AL ONE", [500, 500]),
        _rider("b|team a", "BO TWO", [500, 500]),
        _rider("77", "CY THREE", [400, 400]),
    ]
    session = _session("Varsity Boys", [_row(1, "Al One", "5")])
    lists = top_season(riders, top=2, bibs=bibs_from_sessions([session]))
    rows = lists["Varsity Boys"]
    assert [f.rank for f in rows] == [1, 1]
    assert rows[0].bib == "5"  # filled from the race by name + team
    assert rows[1].bib == ""
    assert "avg 500.0 over 2 races" in rows[0].detail


def test_team_contact_maps_school_to_team_finder_entry() -> None:
    from raspberry_pab.race_results.team_contacts import contact_text, team_contact

    contact = team_contact("East Ridge HS")
    assert contact is not None and contact.team == "PWER"
    assert "mailto:racmtbmn@gmail.com" in contact_text("Roseville")
    # no confident match -> falls back to the Team Finder page
    assert "team-finder" in contact_text("Minneapolis Southwest HS")
