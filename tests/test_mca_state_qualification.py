"""Tests for MCA archive discovery, standings/results PDF parsing and qualification."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from raspberry_pab.race_results.mca_archive import (
    latest_standings,
    parse_results_archive,
)
from raspberry_pab.race_results.mca_race_pdf import (
    parse_individual_results_text,
    to_sessions,
)
from raspberry_pab.race_results.mca_scoring import (
    StandingsBucket,
    build_all_standings,
    riders_from_sessions,
)
from raspberry_pab.race_results.mca_standings import (
    StandingsParseError,
    parse_standings_text,
    split_name_team,
)
from raspberry_pab.race_results.state_qualification import (
    NewRace,
    RaceEntry,
    RiderSeason,
    SeasonCell,
    competition_ranks,
    evaluate,
    merge_race,
    place_for_points,
    remaining_by_team,
    riders_from_standings,
    status_for,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mca"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- archive ---------------------------------------------------------------


def test_archive_lists_only_requested_season() -> None:
    docs = parse_results_archive(_read("results_archive_excerpt.html"), season=2026)
    kinds = [doc.kind for doc in docs]
    assert kinds.count("standings") == 4
    assert kinds.count("team_scores") == 3
    assert kinds.count("individual_results") == 2
    assert all("2025" not in doc.url for doc in docs)
    assert all(doc.url.startswith("https://minnesotacycling.org/") for doc in docs)


def test_archive_picks_latest_standings_per_level() -> None:
    docs = parse_results_archive(_read("results_archive_excerpt.html"), season=2026)
    ms = latest_standings(docs, "MS")
    hs = latest_standings(docs, "HS")
    assert ms is not None and ms.through_race == "4" and "MS-through-Race-4" in ms.url
    assert hs is not None and hs.through_race == "4" and "HS-through-Race-4" in hs.url
    team = next(doc for doc in docs if doc.kind == "team_scores" and doc.level)
    assert team.race_label == "1" and team.level == "MS"


# --- standings -------------------------------------------------------------


def test_ms_standings_rows_and_header() -> None:
    table = parse_standings_text(_read("standings_ms_excerpt.txt"))
    assert table.season == 2026
    assert table.through_race == "4"
    assert table.as_of == date(2026, 9, 23)
    assert [c.label for c in table.columns] == ["1", "2", "3A", "3B", "4"]
    by_name = {row.name: row for row in table.rows}
    nora = by_name["NORA WALZ"]
    assert (nora.team, nora.category, nora.rank) == ("Roseville", "6th Grade Girls", 3)
    assert nora.season_score == 490
    assert nora.cells == (None, 490, 490, None, None)
    dixon = by_name["CHARLIE DIXON"]
    assert (dixon.rank, dixon.season_score) == (9, 457.5)
    assert by_name["EVAN HOUGE"].cells == (0, None, 0, None, 0)
    assert by_name["TYLER DOESCHER"].team == "ISD728"


def test_hs_standings_upgrades_short_plates_and_glued_names() -> None:
    table = parse_standings_text(_read("standings_hs_excerpt.txt"))
    assert table.columns == []  # HS PDF has no header row
    by_name = {row.name: row for row in table.rows}
    loe = by_name["HENRY LOE"]
    assert loe.cells == (None, None, 419, None, None)
    assert loe.upgrade_columns == frozenset({1})
    assert by_name["RYLAN O'HEARN"].plate == "9"
    glued = by_name["MATTEO ALEJANDRO-PROVENZANO"]
    assert glued.team == "St Paul Composite - South"


def test_standings_rejects_rows_that_fail_the_average_check() -> None:
    bad = _read("standings_ms_excerpt.txt").replace(
        "NORA WALZ  Roseville  2 6th Grade Girls  3  490",
        "NORA WALZ  Roseville  2 6th Grade Girls  3  480",
    )
    with pytest.raises(StandingsParseError, match="score mismatch"):
        parse_standings_text(bad)


def test_standings_race5_title_layout() -> None:
    text = (
        "      2026 MCA Individual Points through Race 5 10/1/2026\n"
        "            Middle School\n"
        "Rider Plate   Name   Team Name   Team Division   Category   Rank"
        "   Season Score   Race 1 Schindler's Way   Race 2 Xcel Energy\n"
        "   6555   NORA WALZ   Roseville   2 6th Grade Girls   2   495"
        "   490   500\n"
    )
    table = parse_standings_text(text)
    assert (table.season, table.through_race) == (2026, "5")
    assert table.as_of == date(2026, 10, 1)
    assert table.level == "Middle School"
    assert table.rows[0].name == "NORA WALZ"
    assert table.rows[0].team == "Roseville"

    hs = parse_standings_text(
        text.replace(
            "2026 MCA Individual Points through Race 5 10/1/2026",
            "2026 MCA Individual Points",
        ).replace("Middle School", "High School Through Race 5 9/30/2026")
    )
    assert (hs.through_race, hs.as_of) == ("5", date(2026, 9, 30))
    assert hs.level == "High School"


def test_split_name_team_boundary() -> None:
    assert split_name_team("JANE DOE  St Cloud") == ("JANE DOE", "St Cloud")
    assert split_name_team("JO O'NEILLSt Croix") == ("JO O'NEILL", "St Croix")


# --- official race results PDF --------------------------------------------


def test_race_pdf_rows_dnf_penalty_and_names() -> None:
    results = parse_individual_results_text(_read("race2_ms_results.txt"))
    assert results.race_label == "2"
    rows = {row.name: row for row in results.rows}
    assert rows["BRIDGET CASSLEMAN"].team == "BBBikers"
    assert rows["NATHAN (NATE) KROGH"].team == "Totino Grace-Irondale"
    assert rows["OSCAR OATMAN"].dnf and rows["OSCAR OATMAN"].laps == 0
    assert rows["ABRAM HEGGERSTON"].penalty == "5 Min"
    assert rows["NORA WALZ"].plate == "6555" and rows["NORA WALZ"].place == 2


def test_race2_ms_d2_team_scores_match_official_sheet() -> None:
    results = parse_individual_results_text(_read("race2_ms_results.txt"))
    sessions = [
        s
        for s in to_sessions(results, race_date=date(2026, 8, 29))
        if "Grade" in s.category_label
    ]
    day = build_all_standings(riders_from_sessions(sessions))[0]
    ms_d2 = day.buckets[StandingsBucket.MS_D2]
    assert [(s.team_name, s.total_points) for s in ms_d2[:2]] == [
        ("St Louis Park HS", 1917),
        ("St Cloud", 1883),
    ]
    roseville = next(s for s in ms_d2 if s.team_name == "Roseville")
    assert ms_d2.index(roseville) + 1 == 7
    assert roseville.total_points == 1721


# --- qualification ---------------------------------------------------------


def _rider(
    plate: str, team: str, points: list[int | None], category: str = "8th Grade Boys D2"
) -> RiderSeason:
    cells = [
        SeasonCell(
            str(i + 1),
            "bye" if p is None else ("missed" if p == 0 else "race"),
            p,
        )
        for i, p in enumerate(points)
    ]
    return RiderSeason(plate, f"RIDER {plate}", team, category, cells)


def test_riders_from_standings_maps_cells() -> None:
    table = parse_standings_text(_read("standings_hs_excerpt.txt"))
    riders = {r.name: r for r in riders_from_standings(table)}
    loe = riders["HENRY LOE"]
    assert [c.kind for c in loe.cells] == ["bye", "upgrade", "race", "bye", "bye"]
    assert loe.average == 419
    assert loe.starts == 2  # the pre-upgrade race counts toward registration


def test_merge_race_scheduled_missed_bye_and_not_held() -> None:
    riders = [
        _rider("1", "Roseville", [None, 400]),
        _rider("2", "Roseville", [None, 380]),
        _rider("3", "Edina", [420, None]),
        _rider("4", "Roseville", [None, 500], category="Varsity Boys"),
    ]
    race = NewRace(
        label="Theo 9/26",
        entries=[RaceEntry("1", "RIDER 1", "Roseville", "8th Grade Boys D2", 1)],
        held_levels=frozenset({"middle_school"}),
        preliminary=True,
    )
    merge_race(riders, race)
    kinds = {r.plate: r.cells[-1].kind for r in riders}
    assert kinds == {"1": "race", "2": "missed", "3": "bye", "4": "not_held"}
    # a canceled level only uses a slot for teams that were at the event
    edina_varsity = _rider("5", "Edina", [420, None], category="Varsity Boys")
    merge_race([edina_varsity], race)
    assert edina_varsity.cells[-1].kind == "bye"
    assert riders[0].cells[-1].points == 500
    assert riders[1].average == 190  # (380 + 0) / 2


def test_merge_race_dnf_scores_zero_but_counts_as_start() -> None:
    riders = [_rider("1", "Roseville", [400])]
    race = NewRace(
        "R",
        [RaceEntry("1", "RIDER 1", "Roseville", "8th Grade Boys D2", 60, dnf=True)],
        frozenset({"middle_school"}),
        preliminary=False,
    )
    merge_race(riders, race)
    assert riders[0].cells[-1].kind == "dnf"
    assert (riders[0].average, riders[0].starts) == (200, 2)


def test_merge_race_matches_new_plate_by_name_and_team() -> None:
    clara = RiderSeason(
        "4568",
        "CLARA WALZ",
        "Roseville",
        "Freshman Girls",
        [SeasonCell("2", "race", 472), SeasonCell("3A", "race", 456)],
    )
    other = RiderSeason(
        "4600", "CLARA WALZ", "Edina", "Freshman Girls", [SeasonCell("2", "bye", None)]
    )
    race = NewRace(
        "Cuyuna 10/3",
        [RaceEntry("3585", "Clara Walz", "Roseville", "Freshman Girls", 7)],
        frozenset({"high_school"}),
        preliminary=True,
    )
    riders = merge_race([clara, other], race)
    assert len(riders) == 2  # no duplicate "new rider" row for plate 3585
    assert (clara.cells[-1].kind, clara.cells[-1].points) == ("race", 448)
    assert any("plate 3585" in flag for flag in clara.flags)
    assert other.cells[-1].kind == "bye"


def test_competition_ranks_share_ties() -> None:
    assert competition_ranks({"a": 500, "b": 490, "c": 490, "d": 480}) == {
        "a": 1,
        "b": 2,
        "c": 2,
        "d": 4,
    }


def test_status_thresholds() -> None:
    assert status_for(5, 150, 2) == "ON TRACK"
    assert status_for(95, 150, 2) == "BUBBLE"
    assert status_for(110, 150, 2) == "BUBBLE"
    assert status_for(111, 150, 2) == "OFF TRACK"
    assert status_for(140, 80, 2) == "ON TRACK"  # field under 100: all in
    assert status_for(3, 150, 1) == "NEEDS RACES"


def test_tie_at_cutoff_is_inside() -> None:
    riders = [_rider(str(i), "T", [500 - i]) for i in range(99)]
    riders += [_rider("x", "T", [300]), _rider("y", "T", [300]), _rider("z", "T", [1])]
    results = evaluate(riders, remaining=None)
    assert results["x"].rank == results["y"].rank == 100


def test_place_for_points_uses_appendix_a() -> None:
    assert place_for_points(500, "base") == 1
    assert place_for_points(481, "base") == 3
    assert place_for_points(482, "base") == 2
    assert place_for_points(576, "varsity") is None


def test_projection_and_points_needed() -> None:
    # 120 riders averaging 400..281; our rider has two 0s dragging them down.
    riders = [_rider(str(i), "T", [400 - i] * 4) for i in range(120)]
    riders.append(_rider("me", "Roseville", [420, 420, 0, 0]))
    results = evaluate(riders, remaining=2)
    me = results["me"]
    assert me.rider.average == 210
    assert me.status == "OFF TRACK"
    assert me.projected_average == pytest.approx((840 + 2 * 420) / 6)
    assert me.cutoff_average == 301
    # needs (301 * 6 - 840) / 2 = 483 per race -> 2nd place on the base grid
    assert me.points_needed == pytest.approx(483)
    assert me.place_needed == 2


def test_remaining_races_from_four_race_cap() -> None:
    riders = [
        # Roseville: raced R2, R3A, canceled HS level at R5 -> 3 used, 1 left
        _rider("1", "Roseville", [None, 400, 380, None]),
        _rider("2", "Roseville", [None, 0, 390, None]),
        _rider("3", "Edina", [420, 410, None, None]),
        _rider("4", "Stillwater", [400, 400, 400, 400]),
    ]
    riders[0].cells[3] = SeasonCell("5", "not_held", None)
    assert remaining_by_team(riders) == {"roseville": 1, "edina": 2, "stillwater": 0}


def test_projection_uses_each_teams_remaining() -> None:
    riders = [_rider(str(i), "T", [400 - i] * 4) for i in range(120)]
    riders.append(_rider("me", "Roseville", [420, 420, 0, 0]))
    results = evaluate(riders, remaining={"roseville": 1, "t": 0})
    me = results["me"]
    assert me.remaining == 1
    assert results["0"].remaining == 0
    assert results["0"].points_needed is None
    # (301 * 5 - 840) / 1 = 665 per race: out of reach on the base grid
    assert me.points_needed == pytest.approx(665)
    assert me.place_needed is None
