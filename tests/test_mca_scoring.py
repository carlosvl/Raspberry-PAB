"""Tests for MCA Appendix A scoring and team combinations."""

from __future__ import annotations

from datetime import date
from typing import Literal

from tests.race_results_helpers import load_fixture

from raspberry_pab.race_results.itsyourrace import (
    ParsedIyrSession,
    ParsedResultRow,
    parse_category_options,
)
from raspberry_pab.race_results.mca_scoring import (
    Gender,
    SchoolLevel,
    ScoredRider,
    StandingsBucket,
    build_all_standings,
    gender_mix_string,
    infer_team_division,
    parse_category_label,
    points_for_place,
    riders_from_sessions,
    score_team,
    select_scoring_riders,
)

FieldDivision = Literal["D1", "D2"]


def test_appendix_a_grid_samples() -> None:
    assert points_for_place(1, "varsity") == 575
    assert points_for_place(10, "varsity") == 502
    assert points_for_place(50, "varsity") == 361
    assert points_for_place(51, "varsity") == 360
    assert points_for_place(1, "jv3") == 540
    assert points_for_place(10, "jv3") == 467
    assert points_for_place(50, "jv3") == 326
    assert points_for_place(51, "jv3") == 325
    assert points_for_place(1, "base") == 500
    assert points_for_place(15, "base") == 396
    assert points_for_place(50, "base") == 286
    assert points_for_place(52, "base") == 284


def test_parse_category_labels_from_pine_valley_fixture() -> None:
    html = load_fixture("iyr_pine_valley_default.html")
    options = parse_category_options(html)
    by_label = {option.label: parse_category_label(option.label) for option in options}

    freshman = by_label["Freshman Boys D2"]
    assert freshman.point_column == "base"
    assert freshman.school_level == "high_school"
    assert freshman.gender == "boy"
    assert freshman.field_division == "D2"

    sixth = by_label["6th Grade Girls"]
    assert sixth.point_column == "base"
    assert sixth.school_level == "middle_school"
    assert sixth.gender == "girl"
    assert sixth.field_division is None

    varsity = by_label["Varsity Boys"]
    assert varsity.point_column == "varsity"
    assert varsity.school_level == "high_school"
    assert varsity.gender == "boy"

    jv3 = by_label["JV3 Girls"]
    assert jv3.point_column == "jv3"
    assert jv3.gender == "girl"


def _rider(
    *,
    team: str,
    name: str,
    place: int,
    points: int,
    gender: Gender,
    level: SchoolLevel = "high_school",
    field_division: FieldDivision | None = "D2",
    category: str = "Freshman Boys D2",
) -> ScoredRider:
    return ScoredRider(
        team_name=team,
        raw_name=name,
        bib=None,
        place=place,
        points=points,
        category_label=category,
        race_date=date(2026, 9, 13),
        total_time="00:30:00",
        school_level=level,
        gender=gender,
        field_division=field_division,
        results_url="https://example.test",
        results_status="official",
    )


def test_d2_caps_top_4_max_3_per_gender() -> None:
    riders = [
        _rider(team="Roseville", name="B1", place=1, points=500, gender="boy"),
        _rider(team="Roseville", name="B2", place=2, points=490, gender="boy"),
        _rider(team="Roseville", name="B3", place=3, points=481, gender="boy"),
        _rider(team="Roseville", name="B4", place=4, points=472, gender="boy"),
        _rider(
            team="Roseville",
            name="G1",
            place=1,
            points=500,
            gender="girl",
            category="Freshman Girls",
            field_division=None,
        ),
    ]
    selected = select_scoring_riders(
        riders,
        school_level="high_school",
        division="D2",
    )
    assert len(selected) == 4
    names = {r.raw_name for r in selected}
    assert "B4" not in names  # fourth boy blocked by gender cap of 3
    assert "G1" in names
    assert gender_mix_string(selected) == "BBBG"


def test_d1_caps_top_8_max_6_per_gender() -> None:
    riders = [
        _rider(
            team="Big",
            name=f"B{i}",
            place=i,
            points=500 - i,
            gender="boy",
            field_division="D1",
            category="JV2 Boys D1",
        )
        for i in range(1, 8)
    ] + [
        _rider(
            team="Big",
            name=f"G{i}",
            place=i,
            points=400 - i,
            gender="girl",
            field_division=None,
            category="JV2 Girls",
        )
        for i in range(1, 4)
    ]
    selected = select_scoring_riders(
        riders,
        school_level="high_school",
        division="D1",
    )
    assert len(selected) == 8
    boys = sum(1 for r in selected if r.gender == "boy")
    girls = sum(1 for r in selected if r.gender == "girl")
    assert boys == 6
    assert girls == 2


def test_infer_division_and_unknown_uses_d2_caps() -> None:
    d2 = [_rider(team="A", name="x", place=1, points=500, gender="boy")]
    assert infer_team_division(d2) == "D2"

    combined = [
        _rider(
            team="A",
            name="y",
            place=1,
            points=575,
            gender="boy",
            field_division=None,
            category="Varsity Boys",
        )
    ]
    assert infer_team_division(combined) == "unknown"

    scored = score_team(
        "A",
        combined,
        school_level="high_school",
    )
    assert scored is not None
    assert scored.division == "unknown"
    assert scored.total_points == 575


def test_standings_bucket_roseville_highlighted_path() -> None:
    sessions = [
        ParsedIyrSession(
            series_id="17320",
            season_year=2026,
            eid="1",
            category_label="Freshman Boys D2",
            race_date=date(2026, 9, 13),
            results_status="Unofficial",
            results_url="https://example.test/1",
            rows=[
                ParsedResultRow(
                    place=1,
                    raw_name="Ada Rider",
                    bib="1",
                    team_name="Roseville",
                    laps=3,
                    total_time="00:20:00",
                    total_distance=None,
                ),
                ParsedResultRow(
                    place=2,
                    raw_name="Other Kid",
                    bib="2",
                    team_name="Edina Cycling",
                    laps=3,
                    total_time="00:21:00",
                    total_distance=None,
                ),
            ],
            page_count=1,
        ),
        ParsedIyrSession(
            series_id="17320",
            season_year=2026,
            eid="2",
            category_label="6th Grade Girls",
            race_date=date(2026, 9, 12),
            results_status="Unofficial",
            results_url="https://example.test/2",
            rows=[
                ParsedResultRow(
                    place=5,
                    raw_name="Maya Rider",
                    bib="3",
                    team_name="Roseville",
                    laps=2,
                    total_time="00:25:00",
                    total_distance=None,
                ),
            ],
            page_count=1,
        ),
    ]
    riders = riders_from_sessions(sessions)
    assert len(riders) == 3
    days = build_all_standings(riders)
    assert [d.race_date for d in days] == [date(2026, 9, 12), date(2026, 9, 13)]

    sat = days[0]
    assert len(sat.buckets[StandingsBucket.MS_D2]) == 1
    assert sat.buckets[StandingsBucket.MS_D2][0].team_name == "Roseville"
    assert sat.buckets[StandingsBucket.MS_D2][0].total_points == points_for_place(
        5, "base"
    )

    sun = days[1]
    hs = sun.buckets[StandingsBucket.HS_D2]
    assert [t.team_name for t in hs] == ["Roseville", "Edina Cycling"]
    assert hs[0].total_points == 500
