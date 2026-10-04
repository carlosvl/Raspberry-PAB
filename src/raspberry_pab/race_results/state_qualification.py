"""State Championship qualification (2026 MCA Ch. 11).

Starts from MCA's official "Individual Points through Race N" standings, merges
races held after that snapshot, re-ranks each category and projects the rest of
the regular season. Top ``cutoff`` (100) per category qualify.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from raspberry_pab.race_results.mca_scoring import (
    PointColumn,
    SchoolLevel,
    parse_category_label,
    points_for_place,
)
from raspberry_pab.race_results.mca_standings import RaceColumn, StandingsTable
from raspberry_pab.race_results.names import names_match

CellKind = Literal["race", "missed", "dnf", "bye", "upgrade", "not_held"]
Status = Literal["ON TRACK", "BUBBLE", "OFF TRACK", "NEEDS RACES"]

QUALIFY_CUTOFF = 100
BUBBLE_MARGIN = 10
MAX_REGULAR_RACES = 4  # each team races at most 4 regular-season races (user)
_COUNTED: frozenset[CellKind] = frozenset({"race", "missed", "dnf"})


def normalize_team(name: str) -> str:
    return " ".join(name.lower().split())


@dataclass(frozen=True)
class SeasonCell:
    label: str
    kind: CellKind
    points: int | None
    preliminary: bool = False


@dataclass
class RiderSeason:
    plate: str
    name: str
    team: str
    category: str
    cells: list[SeasonCell]
    flags: list[str] = field(default_factory=list)

    @property
    def level(self) -> SchoolLevel:
        return parse_category_label(self.category).school_level

    @property
    def point_column(self) -> PointColumn:
        return parse_category_label(self.category).point_column

    @property
    def counted(self) -> int:
        return sum(1 for cell in self.cells if cell.kind in _COUNTED)

    @property
    def total(self) -> int:
        return sum(cell.points or 0 for cell in self.cells if cell.kind in _COUNTED)

    @property
    def average(self) -> float:
        return self.total / self.counted if self.counted else 0.0

    @property
    def finishes(self) -> list[int]:
        return [cell.points or 0 for cell in self.cells if cell.kind == "race"]

    @property
    def starts(self) -> int:
        """Races entered, including ones before a category upgrade (registration)."""
        return sum(1 for cell in self.cells if cell.kind in ("race", "dnf", "upgrade"))


@dataclass(frozen=True)
class RaceEntry:
    plate: str
    name: str
    team: str
    category: str
    place: int
    dnf: bool = False

    @property
    def points(self) -> int:
        if self.dnf:
            return 0
        column = parse_category_label(self.category).point_column
        return points_for_place(self.place, column)


@dataclass(frozen=True)
class NewRace:
    """One post-snapshot race weekend.

    ``held_levels`` are the levels that count; a level missing from it is
    left out of every average (Ch. 11 p. 19) but still uses a race slot for
    teams that were there. ``canceled_levels`` marks the confirmed
    cancellations (vs. results not posted yet).
    """

    label: str
    entries: list[RaceEntry]
    held_levels: frozenset[SchoolLevel]
    preliminary: bool
    canceled_levels: frozenset[SchoolLevel] = frozenset()


def riders_from_standings(table: StandingsTable) -> list[RiderSeason]:
    labels = [column.label for column in table.columns]
    riders: list[RiderSeason] = []
    for row in table.rows:
        cells: list[SeasonCell] = []
        for index, value in enumerate(row.cells):
            label = labels[index] if index < len(labels) else f"#{index + 1}"
            if value is None:
                kind: CellKind = "upgrade" if index in row.upgrade_columns else "bye"
            elif value == 0:
                kind = "missed"
            else:
                kind = "race"
            cells.append(SeasonCell(label=label, kind=kind, points=value))
        riders.append(
            RiderSeason(
                plate=row.plate,
                name=row.name,
                team=row.team,
                category=row.category,
                cells=cells,
            )
        )
    return riders


def merge_race(riders: list[RiderSeason], race: NewRace) -> list[RiderSeason]:
    """Add one post-snapshot race column (MCA rules: scheduled→0, else bye)."""
    by_plate = {entry.plate: entry for entry in race.entries}
    scheduled = {normalize_team(entry.team) for entry in race.entries}
    prior_labels = [cell.label for cell in riders[0].cells] if riders else []
    known = {rider.plate for rider in riders}

    # Riders sometimes race on a new plate (e.g. after moving up a level);
    # match those by name + team when exactly one standings row fits.
    renumbered: dict[str, RaceEntry] = {}
    matched: set[str] = set()
    for new_plate in race.entries:
        if new_plate.plate in known:
            continue
        candidates = [
            rider
            for rider in riders
            if rider.plate not in by_plate
            and rider.plate not in renumbered
            and normalize_team(rider.team) == normalize_team(new_plate.team)
            and names_match(new_plate.name, rider.name)
        ]
        if len(candidates) == 1:
            renumbered[candidates[0].plate] = new_plate
            matched.add(new_plate.plate)

    for rider in riders:
        entry = by_plate.get(rider.plate)
        if entry is None and rider.plate in renumbered:
            entry = renumbered[rider.plate]
            rider.flags.append(
                f"raced {race.label} on plate {entry.plate} (standings: "
                f"{rider.plate}) — matched by name"
            )
        if rider.level not in race.held_levels:
            # Canceled for this level: uses a race slot only for teams that were
            # there (they appear at the other level); everyone else had a bye.
            kind_nh: CellKind = (
                "not_held" if normalize_team(rider.team) in scheduled else "bye"
            )
            cell = SeasonCell(race.label, kind_nh, None, race.preliminary)
        elif entry is not None:
            if entry.category != rider.category:
                rider.flags.append(
                    f"raced {entry.category} at {race.label} (standings: "
                    f"{rider.category}) — category change, verify"
                )
            kind: CellKind = "dnf" if entry.dnf else "race"
            cell = SeasonCell(race.label, kind, entry.points, race.preliminary)
        elif normalize_team(rider.team) in scheduled:
            cell = SeasonCell(race.label, "missed", 0, race.preliminary)
        else:
            cell = SeasonCell(race.label, "bye", None, race.preliminary)
        rider.cells.append(cell)

    for entry in race.entries:
        if entry.plate in known or entry.plate in matched:
            continue
        cells = [SeasonCell(label, "bye", None) for label in prior_labels]
        kind = "dnf" if entry.dnf else "race"
        cells.append(SeasonCell(race.label, kind, entry.points, race.preliminary))
        riders.append(
            RiderSeason(
                plate=entry.plate,
                name=entry.name,
                team=entry.team,
                category=entry.category,
                cells=cells,
                flags=["not in the MCA standings snapshot (new rider?)"],
            )
        )
    return riders


def races_used(riders: list[RiderSeason]) -> dict[str, int]:
    """Race weekends each team was scheduled for (incl. canceled ones)."""
    used: dict[str, set[int]] = {}
    for rider in riders:
        slots = used.setdefault(normalize_team(rider.team), set())
        for index, cell in enumerate(rider.cells):
            if cell.kind != "bye":
                slots.add(index)
    return {team: len(slots) for team, slots in used.items()}


def remaining_by_team(
    riders: list[RiderSeason], *, max_races: int = MAX_REGULAR_RACES
) -> dict[str, int]:
    return {team: max(0, max_races - used) for team, used in races_used(riders).items()}


def competition_ranks(values: dict[str, float]) -> dict[str, int]:
    """Rank keys by value descending; ties share the best rank (1, 2, 2, 4)."""
    ordered = sorted(values.items(), key=lambda item: -item[1])
    ranks: dict[str, int] = {}
    previous: float | None = None
    rank = 0
    for position, (key, value) in enumerate(ordered, start=1):
        if previous is None or abs(value - previous) > 1e-9:
            rank = position
            previous = value
        ranks[key] = rank
    return ranks


def status_for(
    rank: int,
    field_size: int,
    starts: int,
    *,
    cutoff: int = QUALIFY_CUTOFF,
    margin: int = BUBBLE_MARGIN,
) -> Status:
    if starts < 2:
        return "NEEDS RACES"
    if field_size <= cutoff or rank < cutoff - margin:
        return "ON TRACK"
    if rank <= cutoff + margin:
        return "BUBBLE"
    return "OFF TRACK"


def place_for_points(points_needed: float, column: PointColumn) -> int | None:
    """Worst finishing place that still earns ``points_needed`` (None = impossible)."""
    if points_for_place(1, column) < points_needed:
        return None
    place = 1
    while points_for_place(place + 1, column) >= points_needed and place < 400:
        place += 1
    return place


@dataclass(frozen=True)
class Qualification:
    rider: RiderSeason
    rank: int
    field_size: int
    status: Status
    cutoff_average: float | None
    remaining: int | None
    projected_average: float | None
    projected_rank: int | None
    projected_status: Status | None
    points_needed: float | None
    place_needed: int | None


def _cutoff_value(values: list[float], cutoff: int) -> float | None:
    ordered = sorted(values, reverse=True)
    return ordered[cutoff - 1] if len(ordered) > cutoff else None


def evaluate(
    riders: list[RiderSeason],
    *,
    remaining: Mapping[str, int] | int | None,
    cutoff: int = QUALIFY_CUTOFF,
) -> dict[str, Qualification]:
    """Rank every rider in their category and project their remaining races.

    ``remaining`` is races left per team (normalized name), one number for
    everyone, or None to skip the projection.
    """

    def left(rider: RiderSeason) -> int | None:
        if remaining is None or isinstance(remaining, int):
            return remaining
        return remaining.get(normalize_team(rider.team), 0)

    by_category: dict[str, list[RiderSeason]] = {}
    for rider in riders:
        by_category.setdefault(rider.category, []).append(rider)

    results: dict[str, Qualification] = {}
    for group in by_category.values():
        current = {rider.plate: rider.average for rider in group}
        ranks = competition_ranks(current)
        cutoff_now = _cutoff_value(list(current.values()), cutoff)
        projected: dict[str, float] = {}
        if remaining is not None:
            for rider in group:
                r = left(rider) or 0
                form = (
                    sum(rider.finishes) / len(rider.finishes) if rider.finishes else 0
                )
                counted = rider.counted + r
                projected[rider.plate] = (
                    (rider.total + r * form) / counted if counted else 0.0
                )
        projected_ranks = competition_ranks(projected) if projected else {}
        cutoff_later = _cutoff_value(list(projected.values()), cutoff)
        size = len(group)
        for rider in group:
            r_left = left(rider)
            points_needed: float | None = None
            place_needed: int | None = None
            if r_left and cutoff_later is not None:
                points_needed = (
                    cutoff_later * (rider.counted + r_left) - rider.total
                ) / r_left
                if points_needed > 0:
                    place_needed = place_for_points(points_needed, rider.point_column)
            projected_rank = projected_ranks.get(rider.plate)
            results[rider.plate] = Qualification(
                rider=rider,
                rank=ranks[rider.plate],
                field_size=size,
                status=status_for(
                    ranks[rider.plate], size, rider.starts, cutoff=cutoff
                ),
                cutoff_average=cutoff_now,
                remaining=r_left,
                projected_average=projected.get(rider.plate),
                projected_rank=projected_rank,
                projected_status=(
                    status_for(
                        projected_rank,
                        size,
                        rider.starts + (r_left or 0),
                        cutoff=cutoff,
                    )
                    if projected_rank is not None
                    else None
                ),
                points_needed=points_needed,
                place_needed=place_needed,
            )
    return results


def column_labels(tables: list[StandingsTable]) -> list[RaceColumn]:
    """Race columns from whichever standings table has a header."""
    for table in tables:
        if table.columns:
            return table.columns
    return []
