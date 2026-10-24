"""Tests for the State qualification what-if (category move)."""

from __future__ import annotations

from datetime import date

import pytest

from raspberry_pab.race_results.itsyourrace import ParsedIyrSession, ParsedResultRow
from raspberry_pab.race_results.mca_scoring import points_for_place
from raspberry_pab.race_results.state_qualification import (
    RiderSeason,
    SeasonCell,
    evaluate,
)
from raspberry_pab.race_results.state_whatif import (
    WhatIfError,
    distance_ratio,
    move_category,
    place_for_exact_points,
)


def _row(place: int, name: str, bib: str, time: str, miles: str) -> ParsedResultRow:
    return ParsedResultRow(place, name, bib, "Team", 3, time, f"{miles} miles")


def _session(category: str, rows: list[ParsedResultRow]) -> ParsedIyrSession:
    return ParsedIyrSession(
        "1", 2026, "e", category, date(2026, 9, 13), "Unofficial", "u", rows, 1
    )


def _rider(plate: str, category: str, points: int) -> RiderSeason:
    return RiderSeason(
        plate, f"RIDER {plate}", "Team", category, [SeasonCell("R", "race", points)]
    )


def _race() -> dict[str, list[ParsedIyrSession]]:
    jv3 = _session(
        "JV3 Boys",
        [
            _row(1, "RIDER J1", "J1", "00:30:00.0", "9.00"),
            _row(2, "CARLOS MATEO", "9", "00:36:00.0", "9.00"),
            _row(3, "RIDER J3", "J3", "00:40:00.0", "9.00"),
        ],
    )
    varsity = _session(
        "Varsity Boys",
        [
            _row(1, "RIDER V1", "V1", "00:40:00.0", "12.00"),
            _row(2, "RIDER V2", "V2", "00:47:00.0", "12.00"),
            _row(3, "RIDER V3", "V3", "00:49:00.0", "12.00"),
        ],
    )
    return {"R": [jv3, varsity]}


def _field() -> list[RiderSeason]:
    return [
        _rider("J1", "JV3 Boys", points_for_place(1, "jv3")),
        _rider("9", "JV3 Boys", points_for_place(2, "jv3")),
        _rider("J3", "JV3 Boys", points_for_place(3, "jv3")),
        _rider("V1", "Varsity Boys", points_for_place(1, "varsity")),
        _rider("V2", "Varsity Boys", points_for_place(2, "varsity")),
        _rider("V3", "Varsity Boys", points_for_place(3, "varsity")),
    ]


def test_place_for_exact_points_inverts_the_grid() -> None:
    for place in (1, 17, 50, 51, 90):
        points = points_for_place(place, "varsity")
        assert place_for_exact_points(points, "varsity") == place
    with pytest.raises(WhatIfError):
        place_for_exact_points(10_000, "jv3")


def test_distance_ratio_from_iyr_and_none_when_equal() -> None:
    jv3, varsity = _race()["R"]
    assert distance_ratio(jv3, varsity) == pytest.approx(4 / 3)
    assert distance_ratio(jv3, jv3) is None


def test_move_category_slots_athlete_and_shifts_both_fields() -> None:
    riders = _field()
    athlete = riders[1]
    moved, moves = move_category(
        riders, athlete=athlete, new_category="Varsity Boys", sessions_by_label=_race()
    )
    # 36:00 x 4/3 = 48:00 -> between V2 (47:00) and V3 (49:00)
    assert moves[0].new_place == 3
    points = {r.plate: (r.category, r.cells[0].points) for r in moved}
    assert points["9"] == ("Varsity Boys", points_for_place(3, "varsity"))
    assert points["V2"][1] == points_for_place(2, "varsity")  # ahead: unchanged
    assert points["V3"][1] == points_for_place(4, "varsity")  # behind: one down
    assert points["J1"][1] == points_for_place(1, "jv3")
    assert points["J3"][1] == points_for_place(2, "jv3")  # moves up
    assert athlete.category == "JV3 Boys"  # input not mutated
    ranks = evaluate(moved, remaining=None)
    assert ranks["9"].field_size == 4


def test_fatigue_and_override_ratio() -> None:
    riders = _field()
    _, slow = move_category(
        riders,
        athlete=riders[1],
        new_category="Varsity Boys",
        sessions_by_label=_race(),
        fatigue=1.1,
    )
    assert slow[0].new_place == 4  # 52:48 is behind everyone
    _, given = move_category(
        riders,
        athlete=riders[1],
        new_category="Varsity Boys",
        sessions_by_label=_race(),
        ratio_override=1.25,
    )
    assert given[0].ratio_source == "given"
    assert given[0].new_place == 2  # 45:00


def test_missing_race_results_raise() -> None:
    riders = _field()
    with pytest.raises(WhatIfError, match="race R"):
        move_category(
            riders,
            athlete=riders[1],
            new_category="Varsity Boys",
            sessions_by_label={},
        )
