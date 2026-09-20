"""MCA 2026 Chapter 11 team scoring and Appendix A point grid."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Literal

from raspberry_pab.race_results.itsyourrace import ParsedIyrSession, ParsedResultRow

PointColumn = Literal["varsity", "jv3", "base"]
SchoolLevel = Literal["high_school", "middle_school"]
Gender = Literal["boy", "girl"]
TeamDivision = Literal["D1", "D2", "unknown"]

# Appendix A – Scoring Grid (bonuses already baked into Varsity / JV3 columns).
_VARSITY: dict[int, int] = {
    1: 575,
    2: 565,
    3: 556,
    4: 547,
    5: 539,
    6: 531,
    7: 523,
    8: 516,
    9: 509,
    10: 502,
    11: 495,
    12: 489,
    13: 483,
    14: 477,
    15: 471,
    16: 465,
    17: 460,
    18: 455,
    19: 450,
    20: 445,
    21: 440,
    22: 435,
    23: 431,
    24: 427,
    25: 423,
    26: 419,
    27: 415,
    28: 411,
    29: 407,
    30: 404,
    31: 401,
    32: 398,
    33: 395,
    34: 392,
    35: 389,
    36: 386,
    37: 383,
    38: 381,
    39: 379,
    40: 377,
    41: 375,
    42: 373,
    43: 371,
    44: 369,
    45: 367,
    46: 365,
    47: 364,
    48: 363,
    49: 362,
    50: 361,
}
_JV3: dict[int, int] = {
    1: 540,
    2: 530,
    3: 521,
    4: 512,
    5: 504,
    6: 496,
    7: 488,
    8: 481,
    9: 474,
    10: 467,
    11: 460,
    12: 454,
    13: 448,
    14: 442,
    15: 436,
    16: 430,
    17: 425,
    18: 420,
    19: 415,
    20: 410,
    21: 405,
    22: 400,
    23: 396,
    24: 392,
    25: 388,
    26: 384,
    27: 380,
    28: 376,
    29: 372,
    30: 369,
    31: 366,
    32: 363,
    33: 360,
    34: 357,
    35: 354,
    36: 351,
    37: 348,
    38: 346,
    39: 344,
    40: 342,
    41: 340,
    42: 338,
    43: 336,
    44: 334,
    45: 332,
    46: 330,
    47: 329,
    48: 328,
    49: 327,
    50: 326,
}
_BASE: dict[int, int] = {
    1: 500,
    2: 490,
    3: 481,
    4: 472,
    5: 464,
    6: 456,
    7: 448,
    8: 441,
    9: 434,
    10: 427,
    11: 420,
    12: 414,
    13: 408,
    14: 402,
    15: 396,
    16: 390,
    17: 385,
    18: 380,
    19: 375,
    20: 370,
    21: 365,
    22: 360,
    23: 356,
    24: 352,
    25: 348,
    26: 344,
    27: 340,
    28: 336,
    29: 332,
    30: 329,
    31: 326,
    32: 323,
    33: 320,
    34: 317,
    35: 314,
    36: 311,
    37: 308,
    38: 306,
    39: 304,
    40: 302,
    41: 300,
    42: 298,
    43: 296,
    44: 294,
    45: 292,
    46: 290,
    47: 289,
    48: 288,
    49: 287,
    50: 286,
}
_GRIDS: dict[PointColumn, dict[int, int]] = {
    "varsity": _VARSITY,
    "jv3": _JV3,
    "base": _BASE,
}

_MS_GRADE = re.compile(r"\b(6th|7th|8th)\b", re.IGNORECASE)
_GENDER = re.compile(r"\b(boys?|girls?)\b", re.IGNORECASE)
_DIVISION = re.compile(r"\bD([12])\b", re.IGNORECASE)


class StandingsBucket(StrEnum):
    HS_D1 = "hs_d1"
    HS_D2 = "hs_d2"
    MS_D1 = "ms_d1"
    MS_D2 = "ms_d2"


@dataclass(frozen=True)
class ParsedCategory:
    label: str
    point_column: PointColumn
    school_level: SchoolLevel
    gender: Gender | None
    field_division: Literal["D1", "D2"] | None


@dataclass(frozen=True)
class ScoredRider:
    team_name: str
    raw_name: str
    bib: str | None
    place: int
    points: int
    category_label: str
    race_date: date
    total_time: str | None
    school_level: SchoolLevel
    gender: Gender
    field_division: Literal["D1", "D2"] | None
    results_url: str
    results_status: str


@dataclass(frozen=True)
class TeamScore:
    team_name: str
    school_level: SchoolLevel
    division: TeamDivision
    total_points: int
    gender_mix: str
    scoring_riders: list[ScoredRider]
    all_riders: list[ScoredRider]
    division_inferred: bool


@dataclass(frozen=True)
class DayStandings:
    race_date: date
    buckets: dict[StandingsBucket, list[TeamScore]]


def points_for_place(place: int, column: PointColumn) -> int:
    if place < 1:
        return 0
    grid = _GRIDS[column]
    if place <= 50:
        return grid[place]
    return grid[50] - (place - 50)


def parse_category_label(label: str) -> ParsedCategory:
    lowered = label.lower()
    if "varsity" in lowered:
        point_column: PointColumn = "varsity"
    elif re.search(r"\bjv\s*3\b", lowered) or "jv3" in lowered.replace(" ", ""):
        point_column = "jv3"
    else:
        point_column = "base"

    if _MS_GRADE.search(label):
        school_level: SchoolLevel = "middle_school"
    else:
        school_level = "high_school"

    gender: Gender | None = None
    gender_match = _GENDER.search(label)
    if gender_match is not None:
        token = gender_match.group(1).lower()
        gender = "girl" if token.startswith("girl") else "boy"

    field_division: Literal["D1", "D2"] | None = None
    div_match = _DIVISION.search(label)
    if div_match is not None:
        field_division = "D1" if div_match.group(1) == "1" else "D2"

    return ParsedCategory(
        label=label,
        point_column=point_column,
        school_level=school_level,
        gender=gender,
        field_division=field_division,
    )


def score_rider(
    row: ParsedResultRow,
    *,
    category: ParsedCategory,
    race_date: date,
    results_url: str,
    results_status: str,
) -> ScoredRider | None:
    team = (row.team_name or "").strip()
    if not team or category.gender is None:
        return None
    return ScoredRider(
        team_name=team,
        raw_name=row.raw_name,
        bib=row.bib,
        place=row.place,
        points=points_for_place(row.place, category.point_column),
        category_label=category.label,
        race_date=race_date,
        total_time=row.total_time,
        school_level=category.school_level,
        gender=category.gender,
        field_division=category.field_division,
        results_url=results_url,
        results_status=results_status,
    )


def riders_from_sessions(sessions: list[ParsedIyrSession]) -> list[ScoredRider]:
    riders: list[ScoredRider] = []
    for session in sessions:
        category = parse_category_label(session.category_label)
        for row in session.rows:
            scored = score_rider(
                row,
                category=category,
                race_date=session.race_date,
                results_url=session.results_url,
                results_status=session.results_status,
            )
            if scored is not None:
                riders.append(scored)
    return riders


def _score_caps(school_level: SchoolLevel, division: TeamDivision) -> tuple[int, int]:
    """Return (max_scorers, max_per_gender)."""
    if school_level == "high_school" and division == "D1":
        return 8, 6
    return 4, 3


def select_scoring_riders(
    riders: list[ScoredRider],
    *,
    school_level: SchoolLevel,
    division: TeamDivision,
) -> list[ScoredRider]:
    max_total, max_gender = _score_caps(school_level, division)
    ordered = sorted(riders, key=lambda r: (-r.points, r.place, r.raw_name.lower()))
    selected: list[ScoredRider] = []
    boys = 0
    girls = 0
    for rider in ordered:
        if len(selected) >= max_total:
            break
        if rider.gender == "boy":
            if boys >= max_gender:
                continue
            boys += 1
        else:
            if girls >= max_gender:
                continue
            girls += 1
        selected.append(rider)
    return selected


def gender_mix_string(riders: list[ScoredRider]) -> str:
    boys = sum(1 for r in riders if r.gender == "boy")
    girls = sum(1 for r in riders if r.gender == "girl")
    return ("B" * boys) + ("G" * girls)


def infer_team_division(riders: list[ScoredRider]) -> TeamDivision:
    votes = {r.field_division for r in riders if r.field_division is not None}
    if votes == {"D1"}:
        return "D1"
    if votes == {"D2"}:
        return "D2"
    if "D1" in votes and "D2" not in votes:
        return "D1"
    if "D2" in votes and "D1" not in votes:
        return "D2"
    if "D1" in votes and "D2" in votes:
        # Prefer majority of split-field starts.
        d1 = sum(1 for r in riders if r.field_division == "D1")
        d2 = sum(1 for r in riders if r.field_division == "D2")
        if d1 > d2:
            return "D1"
        if d2 > d1:
            return "D2"
        return "unknown"
    return "unknown"


def score_team(
    team_name: str,
    riders: list[ScoredRider],
    *,
    school_level: SchoolLevel,
) -> TeamScore | None:
    level_riders = [r for r in riders if r.school_level == school_level]
    if not level_riders:
        return None
    division = infer_team_division(level_riders)
    scoring_division: TeamDivision = "D2" if division == "unknown" else division
    scoring = select_scoring_riders(
        level_riders,
        school_level=school_level,
        division=scoring_division,
    )
    return TeamScore(
        team_name=team_name,
        school_level=school_level,
        division=division,
        total_points=sum(r.points for r in scoring),
        gender_mix=gender_mix_string(scoring),
        scoring_riders=scoring,
        all_riders=sorted(level_riders, key=lambda r: (-r.points, r.place)),
        division_inferred=division != "unknown",
    )


def _bucket_for(score: TeamScore) -> StandingsBucket | None:
    if score.school_level == "high_school":
        if score.division == "D1":
            return StandingsBucket.HS_D1
        if score.division in {"D2", "unknown"}:
            return StandingsBucket.HS_D2
    else:
        if score.division == "D1":
            return StandingsBucket.MS_D1
        if score.division in {"D2", "unknown"}:
            return StandingsBucket.MS_D2
    return None


def standings_for_date(race_date: date, riders: list[ScoredRider]) -> DayStandings:
    day_riders = [r for r in riders if r.race_date == race_date]
    teams = sorted({r.team_name for r in day_riders}, key=str.lower)
    buckets: dict[StandingsBucket, list[TeamScore]] = {
        StandingsBucket.HS_D1: [],
        StandingsBucket.HS_D2: [],
        StandingsBucket.MS_D1: [],
        StandingsBucket.MS_D2: [],
    }
    for team in teams:
        team_riders = [r for r in day_riders if r.team_name == team]
        for level in ("high_school", "middle_school"):
            scored = score_team(team, team_riders, school_level=level)
            if scored is None:
                continue
            bucket = _bucket_for(scored)
            if bucket is not None:
                buckets[bucket].append(scored)
    for key in buckets:
        buckets[key] = sorted(
            buckets[key],
            key=lambda s: (-s.total_points, s.team_name.lower()),
        )
    return DayStandings(race_date=race_date, buckets=buckets)


def build_all_standings(riders: list[ScoredRider]) -> list[DayStandings]:
    dates = sorted({r.race_date for r in riders})
    return [standings_for_date(d, riders) for d in dates]


def normalize_team_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def filter_team(riders: list[ScoredRider], team_name: str) -> list[ScoredRider]:
    needle = normalize_team_name(team_name)
    return [r for r in riders if normalize_team_name(r.team_name) == needle]
