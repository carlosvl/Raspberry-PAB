"""Parse Precision Race official "Individual Results" PDFs (layout text)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from raspberry_pab.race_results.itsyourrace import ParsedIyrSession, ParsedResultRow
from raspberry_pab.race_results.mca_standings import split_name_team

_RACE_TITLE = re.compile(r"^\s*Race\s+(\d+[AB]?)\s*-\s*(.+?)\s*$", re.IGNORECASE)
_DIVISION = re.compile(r"^\s*Division:\s*(.+?)\s*$")
_ROW = re.compile(
    r"^\s*(?P<place>\d+)\s+(?P<bib>\d{1,5})\s+(?P<who>\S.*?)\s+"
    r"(?P<rider>\d{9})\s+(?P<laps>\d+)(?P<tail>.*)$"
)


@dataclass(frozen=True)
class OfficialResultRow:
    category: str
    place: int
    plate: str
    name: str
    team: str
    laps: int
    dnf: bool
    penalty: str | None


@dataclass(frozen=True)
class OfficialRaceResults:
    race_label: str | None
    title: str | None
    rows: list[OfficialResultRow]


def parse_individual_results_text(text: str) -> OfficialRaceResults:
    race_label: str | None = None
    title: str | None = None
    category: str | None = None
    rows: list[OfficialResultRow] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if race_label is None:
            title_match = _RACE_TITLE.match(line)
            if title_match is not None:
                race_label = title_match.group(1).upper()
                title = line.strip()
                continue
        division = _DIVISION.match(line)
        if division is not None:
            category = division.group(1)
            continue
        match = _ROW.match(line)
        if match is None or category is None:
            continue
        name, team = split_name_team(match.group("who"))
        tail = match.group("tail")
        penalty = re.search(r"\b(\d+\s*Min)\b", tail)
        rows.append(
            OfficialResultRow(
                category=category,
                place=int(match.group("place")),
                plate=match.group("bib"),
                name=name,
                team=team,
                laps=int(match.group("laps")),
                dnf=bool(re.search(r"\bDNF\b", tail)),
                penalty=penalty.group(1) if penalty else None,
            )
        )
    return OfficialRaceResults(race_label=race_label, title=title, rows=rows)


def to_sessions(
    results: OfficialRaceResults,
    *,
    race_date: date,
    series_id: str = "",
    results_url: str = "",
) -> list[ParsedIyrSession]:
    """Adapt finishers (DNFs dropped) to sessions for the team-scoring engine."""
    by_category: dict[str, list[ParsedResultRow]] = {}
    for row in results.rows:
        if row.dnf:
            continue
        by_category.setdefault(row.category, []).append(
            ParsedResultRow(
                place=row.place,
                raw_name=row.name,
                bib=row.plate,
                team_name=row.team,
                laps=row.laps,
                total_time=None,
                total_distance=None,
            )
        )
    return [
        ParsedIyrSession(
            series_id=series_id,
            season_year=race_date.year,
            eid="",
            category_label=category,
            race_date=race_date,
            results_status="Official",
            results_url=results_url,
            rows=rows,
            page_count=1,
        )
        for category, rows in by_category.items()
    ]
