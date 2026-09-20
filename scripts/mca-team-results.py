#!/usr/bin/env python3
"""Scrape ITS YOUR RACE and write MCA team standings markdown for a focus team."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

# Allow running without installing: PYTHONPATH=src
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from raspberry_pab.race_results.mca_scoring import (  # noqa: E402
    DayStandings,
    ScoredRider,
    StandingsBucket,
    TeamScore,
    build_all_standings,
    filter_team,
    normalize_team_name,
    riders_from_sessions,
)
from raspberry_pab.race_results.series_fetch import fetch_series_sessions  # noqa: E402

_BUCKET_TITLES = {
    StandingsBucket.HS_D1: "High School Division I",
    StandingsBucket.HS_D2: "High School Division II",
    StandingsBucket.MS_D1: "Middle School Division I",
    StandingsBucket.MS_D2: "Middle School Division II",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score MCA team results from an ITS YOUR RACE series URL",
    )
    parser.add_argument(
        "--url",
        default="https://www.itsyourrace.com/results.aspx?id=17320",
        help="IYR series results URL (default: id=17320)",
    )
    parser.add_argument(
        "--team",
        default="Roseville",
        help="Team name to highlight (case-insensitive)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_REPO_ROOT / "docs" / "mca-team-results.md",
        help="Markdown output path",
    )
    return parser


def _status_summary(riders: list[ScoredRider]) -> str:
    statuses = sorted({r.results_status for r in riders})
    if not statuses:
        return "unknown"
    return ", ".join(statuses)


def _format_standings_table(
    scores: list[TeamScore],
    *,
    focus_team: str,
) -> list[str]:
    lines = [
        "| Place | Team | Score | Mix | Scorers |",
        "| ---: | --- | ---: | --- | ---: |",
    ]
    focus = normalize_team_name(focus_team)
    for index, score in enumerate(scores, start=1):
        name = score.team_name
        if normalize_team_name(name) == focus:
            name = f"**{name}**"
        note = ""
        if score.division == "unknown":
            note = "†"
        lines.append(
            f"| {index} | {name}{note} | {score.total_points} | "
            f"{score.gender_mix or '—'} | {len(score.scoring_riders)} |"
        )
    if not scores:
        lines.append("| — | *(no teams)* | — | — | — |")
    return lines


def _format_day_section(day: DayStandings, *, focus_team: str) -> list[str]:
    lines = [f"## {day.race_date.isoformat()}", ""]
    for bucket in StandingsBucket:
        lines.append(f"### {_BUCKET_TITLES[bucket]}")
        lines.append("")
        lines.extend(
            _format_standings_table(
                day.buckets[bucket],
                focus_team=focus_team,
            )
        )
        lines.append("")
    return lines


def _format_focus_detail(
    riders: list[ScoredRider],
    days: list[DayStandings],
    *,
    focus_team: str,
) -> list[str]:
    focus_riders = filter_team(riders, focus_team)
    lines = [
        f"## {focus_team} detail",
        "",
        "Riders who counted toward the team score are marked **scoring**.",
        "",
    ]
    if not focus_riders:
        lines.append(f"No finishers found for team `{focus_team}`.")
        lines.append("")
        return lines

    scoring_keys: set[tuple[str, int, str]] = set()
    for day in days:
        for scores in day.buckets.values():
            for score in scores:
                focus_norm = normalize_team_name(focus_team)
                if normalize_team_name(score.team_name) != focus_norm:
                    continue
                for rider in score.scoring_riders:
                    scoring_keys.add(
                        (rider.category_label, rider.place, rider.raw_name)
                    )

    lines.extend(
        [
            "| Date | Category | Place | Name | Time | Points | Role |",
            "| --- | --- | ---: | --- | --- | ---: | --- |",
        ]
    )
    ordered = sorted(
        focus_riders,
        key=lambda r: (r.race_date, r.school_level, -r.points, r.place, r.raw_name),
    )
    for rider in ordered:
        key = (rider.category_label, rider.place, rider.raw_name)
        role = "**scoring**" if key in scoring_keys else "non-scoring"
        time = rider.total_time or "—"
        lines.append(
            f"| {rider.race_date.isoformat()} | {rider.category_label} | "
            f"{rider.place} | {rider.raw_name} | {time} | {rider.points} | {role} |"
        )
    lines.append("")

    for day in days:
        for bucket, scores in day.buckets.items():
            match = next(
                (
                    s
                    for s in scores
                    if normalize_team_name(s.team_name)
                    == normalize_team_name(focus_team)
                ),
                None,
            )
            if match is None:
                continue
            place = scores.index(match) + 1
            div_note = (
                f"division {match.division}"
                if match.division != "unknown"
                else "division unknown (scored with D2 caps)"
            )
            lines.append(
                f"- **{day.race_date.isoformat()}** {_BUCKET_TITLES[bucket]}: "
                f"place **{place}**, score **{match.total_points}**, "
                f"mix `{match.gender_mix or '—'}`, {div_note}."
            )
    lines.append("")
    return lines


def render_markdown(
    *,
    url: str,
    focus_team: str,
    series_id: str,
    season_year: int,
    sessions_count: int,
    skipped: list[str],
    riders: list[ScoredRider],
    days: list[DayStandings],
    scraped_at: datetime,
) -> str:
    lines = [
        f"# MCA team results — {focus_team}",
        "",
        f"- **Series URL:** {url}",
        f"- **Series id:** `{series_id}`",
        f"- **Season year:** {season_year}",
        f"- **Scraped at:** {scraped_at.isoformat()}",
        f"- **Categories synced:** {sessions_count}",
        f"- **Results status:** {_status_summary(riders)}",
        "- **Scoring:** 2026 MCA Chapter 11 team scoring + Appendix A point grid",
        "",
        "Team penalties are not present on ITS YOUR RACE pages and are not applied.",
        "",
        "† Team division could not be inferred from split D1/D2 fields; "
        "scored with Division II / Middle School caps (top 4, max 3 per gender).",
        "",
    ]
    if skipped:
        lines.append("Skipped categories (no posted date/results yet):")
        lines.append("")
        for label in skipped:
            lines.append(f"- {label}")
        lines.append("")

    for day in days:
        lines.extend(_format_day_section(day, focus_team=focus_team))

    lines.extend(_format_focus_detail(riders, days, focus_team=focus_team))
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(f"Fetching {args.url} …", flush=True)
    result = fetch_series_sessions(args.url)
    print(
        f"Synced {len(result.sessions)} categories "
        f"({len(result.skipped_categories)} skipped)",
        flush=True,
    )
    riders = riders_from_sessions(result.sessions)
    days = build_all_standings(riders)
    scraped_at = datetime.now(UTC).astimezone()
    markdown = render_markdown(
        url=args.url,
        focus_team=args.team,
        series_id=result.series_id,
        season_year=result.season_year,
        sessions_count=len(result.sessions),
        skipped=result.skipped_categories,
        riders=riders,
        days=days,
        scraped_at=scraped_at,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    print(f"Wrote {args.out}")
    focus = filter_team(riders, args.team)
    print(f"{args.team} finishers: {len(focus)}")
    for day in days:
        for bucket, scores in day.buckets.items():
            match = next(
                (
                    s
                    for s in scores
                    if normalize_team_name(s.team_name)
                    == normalize_team_name(args.team)
                ),
                None,
            )
            if match is None:
                continue
            place = scores.index(match) + 1
            print(
                f"  {day.race_date} {_BUCKET_TITLES[bucket]}: "
                f"#{place} score={match.total_points} mix={match.gender_mix}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
