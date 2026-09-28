"""Parse MCA "Individual Points through Race N" standings PDFs (layout text)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

# Race cell: None = bye (team not scheduled / race not held), int = points
# (0 = team was scheduled but the rider did not score).
Cell = int | None

_TITLE = re.compile(
    r"MCA\s+(?P<season>\d{4})\s+Individual Points through Race\s+(?P<through>\d+[AB]?)"
    r"\s*-\s*(?P<level>High School|Middle School)\s*-\s*as of\s+(?P<as_of>[\d/]+)",
    re.IGNORECASE,
)
_HEADER_RACE = re.compile(r"Race\s+(\d+[AB]?)\s+(.+?)(?=\s{2,}Race\s+\d|\s*$)")
_CATEGORY = r"(?:\d+th Grade|Freshman|JV2|JV3|Varsity) (?:Boys|Girls)(?: D[12])?"
_ROW = re.compile(
    r"^\s*(?P<plate>\d{1,5})\s+(?P<who>.+?)\s+(?P<div>[12])\s+"
    rf"(?P<cat>{_CATEGORY})\s+(?P<rank>\d+)\s+(?P<score>\d+(?:\.\d+)?)"
    r"\s+(?P<cells>\S.*?)\s*$"
)
_NAME_TEAM_BOUNDARY = re.compile(r"^(.*?[A-Z'’\-).])([A-Z][a-z].*)$")
_UPGRADE = "NA (Upgrade)"


class StandingsParseError(ValueError):
    """Raised when rows can't be parsed or fail the season-score check."""


@dataclass(frozen=True)
class RaceColumn:
    label: str
    venue: str


@dataclass(frozen=True)
class StandingsRow:
    plate: str
    name: str
    team: str
    team_division: int
    category: str
    rank: int
    season_score: float
    cells: tuple[Cell, ...]
    upgrade_columns: frozenset[int]


@dataclass(frozen=True)
class StandingsTable:
    season: int | None
    level: str | None
    through_race: str | None
    as_of: date | None
    columns: list[RaceColumn]
    rows: list[StandingsRow]


def split_name_team(who: str) -> tuple[str, str]:
    """Split ``NAME   Team`` (2+ spaces), else at the ALL-CAPS→Mixed boundary."""
    parts = re.split(r"\s{2,}", who.strip())
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    match = _NAME_TEAM_BOUNDARY.match(who.strip())
    if match is None:
        raise StandingsParseError(f"Can't split name/team: {who!r}")
    return match.group(1).strip(), match.group(2).strip()


def parse_cells(text: str) -> tuple[list[Cell], set[int]]:
    tokens = text.replace(_UPGRADE, "NA").split()
    cells: list[Cell] = []
    upgrades: set[int] = set()
    for index, token in enumerate(tokens):
        if token == "-":
            cells.append(None)
        elif token == "NA":
            cells.append(None)
            upgrades.add(index)
        elif token.isdigit():
            cells.append(int(token))
        else:
            raise StandingsParseError(f"Unexpected race cell {token!r} in {text!r}")
    return cells, upgrades


def season_average(cells: tuple[Cell, ...] | list[Cell]) -> float:
    counted = [cell for cell in cells if cell is not None]
    return sum(counted) / len(counted) if counted else 0.0


def _parse_header(line: str) -> list[RaceColumn]:
    after = line.split("Season Score", 1)[-1]
    return [
        RaceColumn(label=m.group(1).upper(), venue=m.group(2).strip())
        for m in _HEADER_RACE.finditer(after.strip())
    ]


def parse_standings_text(text: str) -> StandingsTable:
    season: int | None = None
    level: str | None = None
    through: str | None = None
    as_of: date | None = None
    columns: list[RaceColumn] = []
    rows: list[StandingsRow] = []
    errors: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("Page "):
            continue
        title = _TITLE.search(stripped)
        if title is not None:
            season = int(title.group("season"))
            level = title.group("level")
            through = title.group("through").upper()
            as_of = datetime.strptime(title.group("as_of"), "%m/%d/%Y").date()
            continue
        if stripped.startswith("Rider Plate"):
            columns = columns or _parse_header(stripped)
            continue
        match = _ROW.match(line)
        if match is None:
            errors.append(f"unparsed: {stripped[:100]}")
            continue
        try:
            name, team = split_name_team(match.group("who"))
            cells, upgrades = parse_cells(match.group("cells"))
        except StandingsParseError as exc:
            errors.append(str(exc))
            continue
        score = float(match.group("score"))
        if abs(season_average(cells) - score) > 0.01:
            errors.append(f"score mismatch ({score} vs cells): {stripped[:100]}")
            continue
        rows.append(
            StandingsRow(
                plate=match.group("plate"),
                name=name,
                team=team,
                team_division=int(match.group("div")),
                category=match.group("cat"),
                rank=int(match.group("rank")),
                season_score=score,
                cells=tuple(cells),
                upgrade_columns=frozenset(upgrades),
            )
        )

    widths = {len(row.cells) for row in rows}
    if len(widths) > 1:
        errors.append(f"inconsistent race column counts: {sorted(widths)}")
    if columns and widths and len(columns) not in widths:
        errors.append(f"header has {len(columns)} races, rows have {sorted(widths)}")
    last_rank: dict[str, int] = {}
    for row in rows:
        if row.rank < last_rank.get(row.category, 0):
            errors.append(f"rank goes backwards in {row.category} at {row.name}")
        last_rank[row.category] = row.rank
    if errors:
        preview = "\n  ".join(errors[:8])
        raise StandingsParseError(f"{len(errors)} standings problem(s):\n  {preview}")
    return StandingsTable(
        season=season,
        level=level,
        through_race=through,
        as_of=as_of,
        columns=columns,
        rows=rows,
    )
