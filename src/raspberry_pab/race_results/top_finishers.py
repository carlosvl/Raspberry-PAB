"""Top-N finishers per HS category, from a race's results or the season standings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus

from raspberry_pab.race_results.itsyourrace import ParsedIyrSession
from raspberry_pab.race_results.mca_scoring import is_dnf, session_max_laps
from raspberry_pab.race_results.names import names_match
from raspberry_pab.race_results.state_qualification import (
    RiderSeason,
    competition_ranks,
    normalize_team,
)
from raspberry_pab.race_results.team_contacts import contact_text

DEFAULT_TOP = 15

# Freshman / JV2 / JV3 / Varsity only (no Senior Open, no 6th-8th grade).
_TARGET = re.compile(
    r"^(Varsity|JV3|JV2|Freshman)\s+(Girls|Boys)(?:\s+D([12]))?$", re.I
)
_LEVEL_ORDER = {"varsity": 0, "jv3": 1, "jv2": 2, "freshman": 3}


@dataclass(frozen=True)
class Finisher:
    rank: int
    name: str
    school: str
    category: str
    bib: str  # "" when unknown
    detail: str  # race: time / laps; season: average and races
    strava_url: str
    search_url: str


def category_key(label: str) -> tuple[int, int, int] | None:
    """Sort key for a wanted category (Varsity first, girls first), else None."""
    match = _TARGET.match(label.strip())
    if match is None:
        return None
    level, gender, division = match.groups()
    return (
        _LEVEL_ORDER[level.lower()],
        0 if gender.lower() == "girls" else 1,
        int(division or 0),
    )


def display_name(raw: str) -> str:
    """Title-case ALL-CAPS or all-lowercase words; fix doubled apostrophes."""
    cleaned = " ".join(raw.replace("''", "'").split())
    return " ".join(
        word.title() if word.isupper() or word.islower() else word
        for word in cleaned.split()
    )


def locator_links(name: str, school: str) -> tuple[str, str]:
    """Strava athlete-search and Google-search links (matched by hand)."""
    strava = f"https://www.strava.com/athletes/search?text={quote_plus(name)}"
    query = quote_plus(f'"{name}" {school} mountain bike')
    return strava, f"https://www.google.com/search?q={query}"


def _finisher(
    rank: int, name: str, school: str, category: str, bib: str, detail: str
) -> Finisher:
    shown = display_name(name)
    strava, search = locator_links(shown, school)
    return Finisher(rank, shown, school, category, bib, detail, strava, search)


def top_race(
    sessions: list[ParsedIyrSession], top: int = DEFAULT_TOP
) -> dict[str, list[Finisher]]:
    """Top finishers per wanted category by place; DNFs are dropped."""
    wanted = [s for s in sessions if category_key(s.category_label) is not None]
    wanted.sort(key=lambda s: category_key(s.category_label) or (9, 9, 9))
    lists: dict[str, list[Finisher]] = {}
    for session in wanted:
        max_laps = session_max_laps(session)
        rows = sorted(
            (r for r in session.rows if not is_dnf(r, max_laps=max_laps)),
            key=lambda r: r.place,
        )
        lists[session.category_label] = [
            _finisher(
                row.place,
                row.raw_name,
                row.team_name or "",
                session.category_label,
                row.bib or "",
                _race_detail(row.total_time, row.laps),
            )
            for row in rows[:top]
        ]
    return lists


def _race_detail(total_time: str | None, laps: int | None) -> str:
    time = (total_time or "").strip()
    lap_text = f"{laps} lap{'s' if laps != 1 else ''}" if laps else ""
    return f"{time} ({lap_text})" if time and lap_text else time or lap_text


def top_season(
    riders: list[RiderSeason],
    top: int = DEFAULT_TOP,
    *,
    bibs: dict[str, list[tuple[str, str]]] | None = None,
) -> dict[str, list[Finisher]]:
    """Top riders per wanted category by season average (ties share a rank).

    ``bibs`` maps ``normalize_team(team)`` to ``[(name, bib)]`` (from a race) and
    fills in the number for rows whose standings plate is synthetic.
    """
    by_category: dict[str, list[RiderSeason]] = {}
    for rider in riders:
        if category_key(rider.category) is not None and rider.counted:
            by_category.setdefault(rider.category, []).append(rider)
    lists: dict[str, list[Finisher]] = {}
    for category in sorted(by_category, key=lambda c: category_key(c) or (9, 9, 9)):
        group = by_category[category]
        ranks = competition_ranks({r.plate: r.average for r in group})
        ordered = sorted(group, key=lambda r: (ranks[r.plate], r.name))
        lists[category] = [
            _finisher(
                ranks[r.plate],
                r.name,
                r.team,
                category,
                _bib_for(r, bibs or {}),
                f"avg {r.average:.1f} over {r.counted} race"
                f"{'s' if r.counted != 1 else ''}"
                f" ({', '.join(str(p) for p in r.finishes) or '-'})",
            )
            for r in ordered[:top]
        ]
    return lists


def _bib_for(rider: RiderSeason, bibs: dict[str, list[tuple[str, str]]]) -> str:
    if rider.plate.isdigit():
        return rider.plate
    for name, bib in bibs.get(normalize_team(rider.team), []):
        if names_match(rider.name, name):
            return bib
    return ""


def bibs_from_sessions(
    sessions: list[ParsedIyrSession],
) -> dict[str, list[tuple[str, str]]]:
    """Team -> [(name, bib)] for every rider with a bib in a race."""
    result: dict[str, list[tuple[str, str]]] = {}
    for session in sessions:
        for row in session.rows:
            if row.bib and row.team_name:
                result.setdefault(normalize_team(row.team_name), []).append(
                    (row.raw_name, row.bib)
                )
    return result


def render_lists(heading: str, lists: dict[str, list[Finisher]]) -> list[str]:
    """Markdown tables, one per category."""
    lines = [f"## {heading}", ""]
    for category, finishers in lists.items():
        lines += [
            f"### {category}",
            "",
            "| # | Name | School | Bib | Result | Find | Team contact |",
            "| ---: | --- | --- | ---: | --- | --- | --- |",
        ]
        for f in finishers:
            lines.append(
                f"| {f.rank} | {f.name} | {f.school} | {f.bib or '—'} | {f.detail} | "
                f"[Strava]({f.strava_url}) · [Google]({f.search_url}) | "
                f"{contact_text(f.school)} |"
            )
        lines.append("")
    return lines
