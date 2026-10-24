"""What-if: re-score one athlete as if they had raced a different category.

The athlete's finishing time in each race is stretched by the distance ratio
between the two categories (e.g. JV3 3 laps -> Varsity 4 laps = 4/3) and an
optional fatigue factor, then slotted into the other category's real finishing
order. Every rider's points shift by one place where the athlete is inserted
(new category) or removed (old category), so the rest of both fields is
re-scored too. The result is a new rider list for ``evaluate``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from raspberry_pab.race_results.itsyourrace import ParsedIyrSession, ParsedResultRow
from raspberry_pab.race_results.mca_scoring import (
    PointColumn,
    is_dnf,
    parse_category_label,
    points_for_place,
    session_max_laps,
)
from raspberry_pab.race_results.names import names_match
from raspberry_pab.race_results.state_qualification import RiderSeason, SeasonCell

_MAX_PLACE = 400
_MILES = re.compile(r"([\d.]+)\s*mi", re.IGNORECASE)


class WhatIfError(ValueError):
    """The scenario can't be computed from the data given (missing race/row)."""


@dataclass(frozen=True)
class MovedRace:
    label: str
    time: str
    projected_seconds: float
    distance_ratio: float
    ratio_source: str
    old_place: int
    old_points: int
    new_place: int
    new_points: int
    new_finishers: int


def time_seconds(text: str | None) -> float | None:
    parts = (text or "").strip().split(":")
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        return None


def format_seconds(seconds: float) -> str:
    total = round(seconds)
    return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"


def place_for_exact_points(points: int, column: PointColumn) -> int:
    """Best place that earns exactly ``points`` (inverse of Appendix A)."""
    for place in range(1, _MAX_PLACE):
        if points_for_place(place, column) == points:
            return place
    raise WhatIfError(f"{points} pts isn't a {column} grid value")


def finishers(session: ParsedIyrSession) -> list[ParsedResultRow]:
    max_laps = session_max_laps(session)
    return [row for row in session.rows if not is_dnf(row, max_laps=max_laps)]


def _winner_miles(session: ParsedIyrSession) -> float | None:
    rows = finishers(session)
    if not rows:
        return None
    match = _MILES.search(min(rows, key=lambda r: r.place).total_distance or "")
    return float(match.group(1)) if match else None


def distance_ratio(old: ParsedIyrSession, new: ParsedIyrSession) -> float | None:
    """New / old race distance from IYR, or None when IYR doesn't tell them apart."""
    old_miles, new_miles = _winner_miles(old), _winner_miles(new)
    if not old_miles or not new_miles or abs(old_miles - new_miles) < 1e-9:
        return None
    return new_miles / old_miles


def _session(
    sessions: Sequence[ParsedIyrSession], category: str, label: str
) -> ParsedIyrSession:
    wanted = category.strip().lower()
    for session in sessions:
        if session.category_label.strip().lower() == wanted:
            return session
    raise WhatIfError(f"no {category} results for race {label}")


def find_row(session: ParsedIyrSession, rider: RiderSeason) -> ParsedResultRow | None:
    """The rider's IYR row: by plate, else by name (plates change mid-season)."""
    for row in session.rows:
        if row.bib == rider.plate:
            return row
    named = [row for row in session.rows if names_match(row.raw_name, rider.name)]
    return named[0] if len(named) == 1 else None


def _shift(
    cell: SeasonCell,
    category: str,
    move: MovedRace,
    old_category: str,
    new_category: str,
) -> SeasonCell:
    """Move a rider one place down (athlete inserted) or up (athlete removed)."""
    if category not in (old_category, new_category) or not cell.points:
        return cell
    column = parse_category_label(category).point_column
    try:
        place = place_for_exact_points(cell.points, column)
    except WhatIfError:
        return cell  # not a grid value (e.g. an official adjustment): leave it
    if category == new_category and place >= move.new_place:
        return replace(cell, points=points_for_place(place + 1, column))
    if category == old_category and place > move.old_place:
        return replace(cell, points=points_for_place(place - 1, column))
    return cell


def move_category(
    riders: Sequence[RiderSeason],
    *,
    athlete: RiderSeason,
    new_category: str,
    sessions_by_label: Mapping[str, Sequence[ParsedIyrSession]],
    fatigue: float = 1.0,
    ratio_override: float | None = None,
) -> tuple[list[RiderSeason], list[MovedRace]]:
    """Return copies of ``riders`` re-scored as if ``athlete`` raced ``new_category``.

    Only the athlete's finished races move; missed races and DNFs stay 0. A race
    whose IYR distances match (some events report one lap for every category)
    borrows the average ratio of the athlete's other races unless
    ``ratio_override`` is given.
    """
    old_category = athlete.category
    old_column = parse_category_label(old_category).point_column
    new_column = parse_category_label(new_category).point_column
    raced = [cell for cell in athlete.cells if cell.kind == "race" and cell.points]
    if not raced:
        raise WhatIfError(f"{athlete.name} has no finished races to move")

    found: list[tuple[SeasonCell, ParsedResultRow, ParsedIyrSession, float | None]]
    found = []
    for cell in raced:
        sessions = sessions_by_label.get(cell.label)
        if sessions is None:
            raise WhatIfError(f"no ITS YOUR RACE results given for race {cell.label}")
        old_session = _session(sessions, old_category, cell.label)
        new_session = _session(sessions, new_category, cell.label)
        row = find_row(old_session, athlete)
        if row is None or time_seconds(row.total_time) is None:
            raise WhatIfError(
                f"{athlete.name} not found in {old_category} at {cell.label}"
            )
        found.append((cell, row, new_session, distance_ratio(old_session, new_session)))

    known = [ratio for *_, ratio in found if ratio is not None]
    fallback = ratio_override or (sum(known) / len(known) if known else None)

    moves: list[MovedRace] = []
    for cell, row, new_session, ratio in found:
        source = "IYR distance"
        if ratio_override is not None:
            ratio, source = ratio_override, "given"
        elif ratio is None:
            if fallback is None:
                raise WhatIfError(
                    f"can't tell {old_category} from {new_category} distance at "
                    f"{cell.label}; pass a distance ratio"
                )
            ratio, source = fallback, "avg of other races"
        projected = (time_seconds(row.total_time) or 0.0) * ratio * fatigue
        field = finishers(new_session)
        new_place = 1 + sum(
            1 for other in field if (time_seconds(other.total_time) or 0) < projected
        )
        moves.append(
            MovedRace(
                label=cell.label,
                time=row.total_time or "",
                projected_seconds=projected,
                distance_ratio=ratio,
                ratio_source=source,
                old_place=place_for_exact_points(cell.points or 0, old_column),
                old_points=cell.points or 0,
                new_place=new_place,
                new_points=points_for_place(new_place, new_column),
                new_finishers=len(field),
            )
        )

    by_label = {move.label: move for move in moves}
    result: list[RiderSeason] = []
    for rider in riders:
        if rider.plate == athlete.plate:
            cells = [
                replace(cell, points=by_label[cell.label].new_points)
                if cell.label in by_label and cell.kind == "race"
                else cell
                for cell in rider.cells
            ]
            result.append(
                replace(rider, category=new_category, cells=cells, flags=[*rider.flags])
            )
            continue
        cells = []
        for cell in rider.cells:
            move = by_label.get(cell.label)
            if move is not None and cell.kind == "race" and cell.points:
                cell = _shift(cell, rider.category, move, old_category, new_category)
            cells.append(cell)
        result.append(replace(rider, cells=cells, flags=[*rider.flags]))
    return result, moves
