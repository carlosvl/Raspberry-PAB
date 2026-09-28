#!/usr/bin/env python3
"""Report which athletes are on track to qualify for the MCA State Championship."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from raspberry_pab.race_results.client import RaceResultsClient  # noqa: E402
from raspberry_pab.race_results.mca_archive import (  # noqa: E402
    ARCHIVE_URL,
    DEFAULT_CACHE_DIR,
    ArchiveDoc,
    fetch_pdf_text,
    latest_standings,
    parse_results_archive,
)
from raspberry_pab.race_results.mca_race_pdf import (  # noqa: E402
    parse_individual_results_text,
)
from raspberry_pab.race_results.mca_scoring import (  # noqa: E402
    SchoolLevel,
    is_dnf,
    session_max_laps,
)
from raspberry_pab.race_results.mca_standings import (  # noqa: E402
    StandingsTable,
    parse_standings_text,
)
from raspberry_pab.race_results.names import names_match  # noqa: E402
from raspberry_pab.race_results.precision_race import (  # noqa: E402
    ParsedRaceEvent,
    parse_precision_race_mca_html,
)
from raspberry_pab.race_results.series_fetch import fetch_series_sessions  # noqa: E402
from raspberry_pab.race_results.state_qualification import (  # noqa: E402
    MAX_REGULAR_RACES,
    NewRace,
    Qualification,
    RaceEntry,
    RiderSeason,
    column_labels,
    evaluate,
    merge_race,
    normalize_team,
    remaining_by_team,
    riders_from_standings,
)
from raspberry_pab.race_results.sync import MCA_INDEX_URL  # noqa: E402

_STATUS_ORDER = ["BUBBLE", "NEEDS RACES", "OFF TRACK", "ON TRACK"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", default="Roseville", help="Team (case-insensitive)")
    parser.add_argument(
        "--athlete",
        action="append",
        default=[],
        help="Athlete name (repeatable). Omit to report the whole team.",
    )
    parser.add_argument("--season", type=int, default=date.today().year)
    parser.add_argument(
        "--max-races",
        type=int,
        default=MAX_REGULAR_RACES,
        help="Regular-season races per team (default 4); remaining = max - used",
    )
    parser.add_argument(
        "--remaining-races",
        type=int,
        default=None,
        help="Override the computed races left for --team",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_REPO_ROOT / "docs" / "mca-state-qualification.md",
    )
    parser.add_argument(
        "--state-event",
        action="append",
        default=[],
        help="IYR series id of the State Championship (never merged; repeatable)",
    )
    parser.add_argument(
        "--canceled",
        action="append",
        default=[],
        metavar="IYR_ID:LEVEL",
        help="Confirmed canceled race day, e.g. 17333:HS (repeatable)",
    )
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--refresh", action="store_true", help="Re-download PDFs")
    return parser


def _venue_key(venue: str) -> str:
    return venue.strip().split()[0].lower()[:4] if venue.strip() else ""


def _race_label(event: ParsedRaceEvent) -> str:
    venue = event.venue_label.split("-")[0].split(",")[0].split()[0].title()
    return f"{venue} {event.date_saturday:%-m/%-d}"


def _official_race(
    event: ParsedRaceEvent, docs: list[ArchiveDoc], cache_dir: Path, refresh: bool
) -> NewRace | None:
    key = _venue_key(event.venue_label)
    for doc in docs:
        haystack = f"{doc.title} {doc.url}".lower()
        if doc.kind != "individual_results" or not key or key not in haystack:
            continue
        results = parse_individual_results_text(
            fetch_pdf_text(doc.url, cache_dir=cache_dir, refresh=refresh)
        )
        if not results.rows:
            continue
        entries = [
            RaceEntry(r.plate, r.name, r.team, r.category, r.place, r.dnf)
            for r in results.rows
        ]
        return _new_race(_race_label(event), entries, preliminary=False)
    return None


def _iyr_race(event: ParsedRaceEvent) -> NewRace | None:
    url = f"{event.iyr_base_url}/results.aspx?id={event.iyr_series_id}"
    result = fetch_series_sessions(url)
    entries: list[RaceEntry] = []
    for session in result.sessions:
        max_laps = session_max_laps(session)
        for row in session.rows:
            if not row.bib or not row.team_name:
                continue
            dnf = is_dnf(row, max_laps=max_laps)
            entries.append(
                RaceEntry(
                    row.bib,
                    row.raw_name,
                    row.team_name,
                    session.category_label,
                    row.place,
                    dnf,
                )
            )
    if not entries:
        return None
    return _new_race(_race_label(event), entries, preliminary=True)


_LEVEL_NAMES: dict[str, SchoolLevel] = {"HS": "high_school", "MS": "middle_school"}


def _level_short(level: SchoolLevel) -> str:
    return "HS" if level == "high_school" else "MS"


def parse_canceled(values: list[str]) -> dict[str, frozenset[SchoolLevel]]:
    canceled: dict[str, set[SchoolLevel]] = {}
    for value in values:
        series, _, level = value.partition(":")
        if level.strip().upper() not in _LEVEL_NAMES:
            raise SystemExit(
                f"--canceled expects IYR_ID:HS or IYR_ID:MS, got {value!r}"
            )
        canceled.setdefault(series.strip(), set()).add(
            _LEVEL_NAMES[level.strip().upper()]
        )
    return {series: frozenset(levels) for series, levels in canceled.items()}


def _new_race(label: str, entries: list[RaceEntry], *, preliminary: bool) -> NewRace:
    from raspberry_pab.race_results.mca_scoring import parse_category_label

    levels = frozenset(parse_category_label(e.category).school_level for e in entries)
    return NewRace(label, entries, levels, preliminary)


def _cell_text(rider: RiderSeason) -> str:
    parts = []
    for cell in rider.cells:
        if cell.kind in ("bye", "not_held"):
            text = "–" if cell.kind == "bye" else "✕"
        elif cell.kind == "upgrade":
            text = "NA"
        elif cell.kind == "dnf":
            text = "DNF 0"
        else:
            text = str(cell.points)
        parts.append(f"{cell.label}: {text}{'*' if cell.preliminary else ''}")
    return "; ".join(parts)


def _ordinal(number: int) -> str:
    if 10 <= number % 100 <= 20:
        return f"{number}th"
    return f"{number}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th') }"


def _projection_text(q: Qualification) -> str:
    if q.remaining is None:
        return "—"
    if q.projected_rank is None:
        return "—"
    left = f"{q.remaining} left" if q.remaining else "no races left"
    text = f"{left}: #{q.projected_rank} ({q.projected_status})"
    if q.points_needed is not None:
        if q.points_needed <= 0:
            text += "; safe even with 0s"
        elif q.place_needed is None:
            text += f"; needs {q.points_needed:.0f} pts/race (out of reach)"
        elif q.place_needed == 1:
            text += f"; needs a win (~{q.points_needed:.0f} pts)"
        elif q.place_needed >= q.field_size:
            text += "; any finish keeps them in"
        else:
            text += (
                f"; needs ~{q.points_needed:.0f} pts/race "
                f"(≈{_ordinal(q.place_needed)} or better)"
            )
    return text


def _cancellation_section(
    team: str, ordered: list[Qualification], remaining: int, max_races: int
) -> list[str]:
    """Explain the denominator math with this team's own schedule."""
    lines = [
        "",
        "## How canceled races count",
        "",
        "Season average = points from the regular-season races the team was "
        "**scheduled for and that were held** ÷ the number of those races "
        "(Ch. 11 p. 19). A missed race counts as 0 and stays in the average. A "
        "canceled race is **left out of both the points and the count** (/3 "
        "instead of /4), but it still uses one of the team's "
        f"{max_races} race slots, so it isn't replaced by another race.",
        "",
    ]
    for level in ("middle_school", "high_school"):
        riders = [q for q in ordered if q.rider.level == level]
        if not riders:
            continue
        sample = max(riders, key=lambda q: q.rider.counted).rider
        held = [c.label for c in sample.cells if c.kind in ("race", "missed", "dnf")]
        canceled = [c.label for c in sample.cells if c.kind == "not_held"]
        final = len(held) + remaining
        text = (
            f"- **{team} {_level_short(level)}:** held so far "
            f"{', '.join(held) or 'none'}"
        )
        if canceled:
            text += f"; canceled {', '.join(canceled)} (not counted)"
        text += (
            f". With {remaining} race(s) left, the final average divides by "
            f"**{final}**."
        )
        lines.append(text)
        best = max(riders, key=lambda q: q.rider.total).rider
        if best.counted:
            lines.append(
                f"  - Example, {best.name.title()}: now {best.total} ÷ "
                f"{best.counted} = {best.average:.1f}; after the last race "
                f"({best.total} + X) ÷ {best.counted + remaining}, so that race "
                f"is worth 1/{best.counted + remaining} of the season."
            )
    lines.append(
        "- Riders on teams that were at the canceled event lose nothing and "
        "gain nothing. Their average simply has one fewer race, so each "
        "remaining race weighs more."
    )
    return lines


def render_report(
    *,
    team: str,
    selected: list[Qualification],
    tables: list[StandingsTable],
    standings_docs: list[ArchiveDoc],
    new_races: list[NewRace],
    skipped_events: list[str],
    state_events: list[str],
    team_remaining: int,
    max_races: int,
    generated: datetime,
) -> str:
    lines = [
        f"# MCA State Championship qualification — {team}",
        "",
        f"- **Generated:** {generated.isoformat(timespec='minutes')}",
        "- **Rule:** top 100 per category (D1/D2 split categories separately) by "
        "season average; ≥2 registered races (2026 Sporting Regulations, Ch. 11).",
        "- **Official standings:**",
    ]
    for doc, table in zip(standings_docs, tables, strict=True):
        lines.append(
            f"  - [{doc.title}]({doc.url}) — through Race {table.through_race}, "
            f"as of {table.as_of}"
        )
    if new_races:
        lines.append("- **Races merged after the snapshot:**")
        for race in new_races:
            source = (
                "ITS YOUR RACE, preliminary (*)" if race.preliminary else "official"
            )
            parts = [f"{_level_short(lv)} counted" for lv in sorted(race.held_levels)]
            for level in ("middle_school", "high_school"):
                if level in race.held_levels:
                    continue
                if level in race.canceled_levels:
                    parts.append(f"{_level_short(level)} **canceled** (confirmed)")
                else:
                    parts.append(
                        f"{_level_short(level)} no results yet (left out until posted)"
                    )
            lines.append(f"  - {race.label}: {'; '.join(parts)} — {source}")
    if skipped_events:
        lines.append(f"- **No results yet:** {', '.join(skipped_events)}")
    if state_events:
        lines.append(
            f"- **State Championship (not a qualifying race):** "
            f"{', '.join(state_events)}"
        )
    lines.append(
        f"- **Races left:** each team races at most {max_races} regular-season "
        f"races; {team} has **{team_remaining}** left (a canceled race still "
        "uses a slot). Other teams are projected with their own count."
    )
    lines += [
        "",
        "Cells: points · `–` bye · `✕` canceled / not held (not counted) · `NA` "
        "before a category upgrade · `*` preliminary.",
        "",
        "| Status | Athlete | Category | Rank | Avg | #100 avg | Projection | Races |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    ordered = sorted(
        selected,
        key=lambda q: (_STATUS_ORDER.index(q.status), q.rider.category, q.rank),
    )
    for q in ordered:
        cutoff = f"{q.cutoff_average:.1f}" if q.cutoff_average is not None else "all in"
        lines.append(
            f"| {q.status} | {q.rider.name.title()} | {q.rider.category} | "
            f"{q.rank}/{q.field_size} | {q.rider.average:.1f} | {cutoff} | "
            f"{_projection_text(q)} | {_cell_text(q.rider)} |"
        )
    lines += _cancellation_section(team, ordered, team_remaining, max_races)
    flagged = [q for q in ordered if q.rider.flags]
    if flagged:
        lines += ["", "## Flags", ""]
        for q in flagged:
            for flag in q.rider.flags:
                lines.append(f"- **{q.rider.name.title()}:** {flag}")
    lines += [
        "",
        "## Caveats",
        "",
        "- A standings `0` can be a missed race or a DNF; `NEEDS RACES` counts "
        "finishes only, so confirm registration with the coach.",
        "- Grade isn't published: an HS senior outside the top 100 can still "
        "race the Senior Open.",
        "- Results marked Unofficial can change; IYR riders with fewer laps may "
        "be DNF (0) or pulled (placed).",
        "- The projection assumes each rider repeats their average finishing "
        "points in every remaining race (at most 4 regular-season races per "
        "team). If MCA shows a canceled race as a bye, that team's count is "
        "one too high.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = RaceResultsClient()
    archive_html = client.fetch_text(ARCHIVE_URL)
    docs = parse_results_archive(archive_html, season=args.season)

    standings_docs: list[ArchiveDoc] = []
    tables: list[StandingsTable] = []
    for level in ("MS", "HS"):
        doc = latest_standings(docs, level)
        if doc is None:
            print(f"No {level} standings posted for {args.season}", file=sys.stderr)
            continue
        text = fetch_pdf_text(doc.url, cache_dir=args.cache_dir, refresh=args.refresh)
        standings_docs.append(doc)
        tables.append(parse_standings_text(text))
    if not tables:
        return 1
    labels = column_labels(tables)
    tables = [
        replace(table, columns=labels) if not table.columns else table
        for table in tables
    ]
    riders: list[RiderSeason] = []
    for table in tables:
        riders.extend(riders_from_standings(table))

    snapshot = max(t.as_of for t in tables if t.as_of is not None)
    events = [
        event
        for event in parse_precision_race_mca_html(
            client.fetch_text(MCA_INDEX_URL), source_url=MCA_INDEX_URL
        )
        if event.season_year == args.season and event.date_saturday > snapshot
    ]
    new_races: list[NewRace] = []
    skipped: list[str] = []
    state_events: list[str] = []
    canceled = parse_canceled(args.canceled)
    for event in sorted(events, key=lambda e: e.date_saturday):
        if event.iyr_series_id.strip() in args.state_event:
            state_events.append(_race_label(event))
            continue
        race = _official_race(event, docs, args.cache_dir, args.refresh)
        if race is None:
            race = _iyr_race(event)
        if race is None:
            skipped.append(_race_label(event))
            continue
        canceled_here = canceled.get(event.iyr_series_id.strip(), frozenset())
        if canceled_here:
            race = replace(
                race,
                held_levels=race.held_levels - canceled_here,
                canceled_levels=canceled_here,
            )
        new_races.append(race)
        riders = merge_race(riders, race)

    team_key = normalize_team(args.team)
    remaining = remaining_by_team(riders, max_races=args.max_races)
    if args.remaining_races is not None:
        remaining[team_key] = args.remaining_races
    results = evaluate(riders, remaining=remaining)
    selected = [
        q
        for q in results.values()
        if normalize_team(q.rider.team) == team_key
        and (
            not args.athlete
            or any(names_match(name, q.rider.name) for name in args.athlete)
        )
    ]
    report = render_report(
        team=args.team,
        selected=selected,
        tables=tables,
        standings_docs=standings_docs,
        new_races=new_races,
        skipped_events=skipped,
        state_events=state_events,
        team_remaining=remaining.get(team_key, args.max_races),
        max_races=args.max_races,
        generated=datetime.now(UTC).astimezone(),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"Wrote {args.out} ({len(selected)} athletes)")
    for q in sorted(selected, key=lambda q: (_STATUS_ORDER.index(q.status), q.rank)):
        print(
            f"  {q.status:<11} {q.rider.name.title():<28} {q.rider.category:<18} "
            f"#{q.rank}/{q.field_size} avg {q.rider.average:.1f}  "
            f"{_projection_text(q)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
