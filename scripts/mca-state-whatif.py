#!/usr/bin/env python3
"""What-if: would an athlete have qualified for State in another category?"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from raspberry_pab.race_results.client import RaceResultsClient  # noqa: E402
from raspberry_pab.race_results.itsyourrace import ParsedIyrSession  # noqa: E402
from raspberry_pab.race_results.names import names_match  # noqa: E402
from raspberry_pab.race_results.series_fetch import fetch_series_sessions  # noqa: E402
from raspberry_pab.race_results.state_qualification import (  # noqa: E402
    QUALIFY_CUTOFF,
    Qualification,
    RiderSeason,
    evaluate,
    normalize_team,
    remaining_by_team,
)
from raspberry_pab.race_results.state_whatif import (  # noqa: E402
    MovedRace,
    WhatIfError,
    format_seconds,
    move_category,
)

DEFAULT_FATIGUE = [1.0, 1.05, 1.10]


def _qualification_module() -> ModuleType:
    path = _REPO_ROOT / "scripts" / "mca-state-qualification.py"
    spec = importlib.util.spec_from_file_location("mca_state_qualification", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up by name
    spec.loader.exec_module(module)
    return module


QUAL = _qualification_module()


def build_parser() -> argparse.ArgumentParser:
    parser: argparse.ArgumentParser = QUAL.build_parser()
    parser.description = __doc__
    parser.add_argument(
        "--to-category",
        required=True,
        help='Category to re-score the athlete in, as MCA names it ("Varsity Boys")',
    )
    parser.add_argument(
        "--race",
        action="append",
        default=[],
        metavar="LABEL=IYR_ID",
        help="IYR series for a standings race column, e.g. 2=17319 (repeatable). "
        "Races merged after the snapshot are mapped automatically.",
    )
    parser.add_argument(
        "--fatigue",
        action="append",
        type=float,
        default=[],
        help="Extra slowdown over the longer race, 1.05 = 5%% (repeatable; "
        "default 1.0, 1.05, 1.10). The first value is the headline scenario.",
    )
    parser.add_argument(
        "--distance-ratio",
        type=float,
        default=None,
        help="New/old race distance (e.g. 1.3333 for 3 -> 4 laps); default: IYR",
    )
    parser.set_defaults(out=_REPO_ROOT / "docs" / "mca-state-whatif.md")
    return parser


def _race_map(values: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for value in values:
        label, _, series = value.partition("=")
        if not label.strip() or not series.strip().isdigit():
            raise SystemExit(f"--race expects LABEL=IYR_ID, got {value!r}")
        mapping[label.strip()] = series.strip()
    return mapping


def _qualifies(q: Qualification) -> bool:
    rank = q.projected_rank if q.projected_rank is not None else q.rank
    status = q.projected_status or q.status
    return status != "NEEDS RACES" and rank <= QUALIFY_CUTOFF


def _rank_text(q: Qualification | None) -> str:
    if q is None:
        return "—"
    verdict = "qualifies" if _qualifies(q) else "out"
    return (
        f"#{q.rank}/{q.field_size} {q.rider.category}, avg {q.rider.average:.1f} "
        f"({verdict})"
    )


def _evaluate(riders: list[RiderSeason], max_races: int) -> dict[str, Qualification]:
    return evaluate(riders, remaining=remaining_by_team(riders, max_races=max_races))


def render(
    *,
    athlete: RiderSeason,
    new_category: str,
    team: str,
    baseline: dict[str, Qualification],
    scenarios: list[tuple[float, dict[str, Qualification], list[MovedRace]]],
    standings_titles: list[str],
) -> str:
    team_key = normalize_team(team)
    old_category = athlete.category
    fatigue, headline, moves = scenarios[0]
    before, after = baseline[athlete.plate], headline[athlete.plate]
    name = athlete.name.title()
    generated = datetime.now(UTC).astimezone()
    lines = [
        f"# What-if: {name} in {new_category} instead of {old_category}",
        "",
        f"- **Generated:** {generated.isoformat(timespec='minutes')}",
        f"- **Standings:** {'; '.join(standings_titles)} + later races merged "
        "(same data as `docs/mca-state-qualification.md`)",
        "- **Method:** each finishing time × (new/old race distance) × fatigue, "
        f"slotted into the real {new_category} finishing order. Riders behind "
        f"them in {new_category} drop one place; riders behind them in "
        f"{old_category} move up one. Everyone is re-ranked.",
        "",
        "## Answer",
        "",
        f"- **Actual:** {_rank_text(before)}",
        f"- **What-if (fatigue {fatigue:.2f}):** {_rank_text(after)}",
        "",
        f"## Race by race (fatigue {fatigue:.2f})",
        "",
        f"| Race | {old_category} time | Distance × | Projected | "
        f"{old_category} place · pts | {new_category} place · pts |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for move in moves:
        lines.append(
            f"| {move.label} | {move.time} | {move.distance_ratio:.3f} "
            f"({move.ratio_source}) | {format_seconds(move.projected_seconds)} | "
            f"{move.old_place} · {move.old_points} | {move.new_place} of "
            f"{move.new_finishers + 1} · {move.new_points} |"
        )
    lines += [
        "",
        "## Sensitivity",
        "",
        "| Fatigue | Avg | Rank | Qualifies |",
        "| --- | ---: | ---: | --- |",
    ]
    for value, results, _ in scenarios:
        q = results[athlete.plate]
        lines.append(
            f"| {value:.2f} | {q.rider.average:.1f} | {q.rank}/{q.field_size} | "
            f"{'yes' if _qualifies(q) else 'no'} |"
        )

    def team_list(results: dict[str, Qualification]) -> set[str]:
        return {
            plate
            for plate, q in results.items()
            if normalize_team(q.rider.team) == team_key and _qualifies(q)
        }

    old_team, new_team = team_list(baseline), team_list(headline)
    lines += [
        "",
        f"## {team} qualifiers",
        "",
        f"**{len(old_team)} → {len(new_team)}**",
        "",
    ]
    changed = [
        plate
        for plate, q in headline.items()
        if normalize_team(q.rider.team) == team_key
        and plate in baseline
        and (
            (plate in old_team) != (plate in new_team)
            or baseline[plate].rank != q.rank
            or plate == athlete.plate
        )
    ]
    if changed:
        lines += ["| Rider | Actual | What-if |", "| --- | --- | --- |"]
        for plate in changed:
            lines.append(
                f"| {headline[plate].rider.name.title()} | "
                f"{_rank_text(baseline[plate])} | {_rank_text(headline[plate])} |"
            )
    crossers = [
        plate
        for plate, q in headline.items()
        if plate != athlete.plate
        and plate in baseline
        and q.rider.category in (old_category, new_category)
        and _qualifies(baseline[plate]) != _qualifies(q)
    ]
    lines += ["", "## Other riders crossing the top-100 line", ""]
    if crossers:
        lines += ["| Rider | Team | Actual | What-if |", "| --- | --- | --- | --- |"]
        for plate in crossers:
            q = headline[plate]
            lines.append(
                f"| {q.rider.name.title()} | {q.rider.team} | "
                f"{_rank_text(baseline[plate])} | {_rank_text(q)} |"
            )
    else:
        lines.append(f"None in {old_category} or {new_category}.")
    lines += [
        "",
        "## Caveats",
        "",
        "- Pace is assumed to hold over the longer distance (times fatigue). "
        "Start position, course and race tactics aren't modeled.",
        "- Places come from ITS YOUR RACE finishing times; official places can "
        "differ slightly (DNFs, penalties).",
        "- Points shift only for riders who finished; missed races and DNFs stay 0.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if len(args.athlete) != 1:
        raise SystemExit("--athlete is required, once")
    fatigue = args.fatigue or DEFAULT_FATIGUE
    client = RaceResultsClient()
    try:
        season = QUAL.load_season(args, client)
        if season is None:
            return 1
        team_key = normalize_team(args.team)
        matches = [
            rider
            for rider in season.riders
            if normalize_team(rider.team) == team_key
            and names_match(args.athlete[0], rider.name)
        ]
        if len(matches) != 1:
            raise SystemExit(
                f"{args.athlete[0]!r} matched {len(matches)} {args.team} riders"
            )
        athlete = matches[0]
        series = {**season.race_series, **_race_map(args.race)}
        sessions: dict[str, list[ParsedIyrSession]] = {}
        for cell in athlete.cells:
            if cell.kind == "race" and cell.label in series:
                series_id = series[cell.label]
                url = f"https://www.itsyourrace.com/results.aspx?id={series_id}"
                sessions[cell.label] = fetch_series_sessions(
                    url, fetch_text=client.fetch_text
                ).sessions
    finally:
        client.close()

    baseline = _evaluate(season.riders, args.max_races)
    scenarios: list[tuple[float, dict[str, Qualification], list[MovedRace]]] = []
    try:
        for value in fatigue:
            riders, moves = move_category(
                season.riders,
                athlete=athlete,
                new_category=args.to_category,
                sessions_by_label=sessions,
                fatigue=value,
                ratio_override=args.distance_ratio,
            )
            scenarios.append((value, _evaluate(riders, args.max_races), moves))
    except WhatIfError as exc:
        raise SystemExit(
            f"{exc} (map standings races with --race LABEL=IYR_ID)"
        ) from exc

    report = render(
        athlete=athlete,
        new_category=args.to_category,
        team=args.team,
        baseline=baseline,
        scenarios=scenarios,
        standings_titles=[doc.title for doc in season.standings_docs],
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"Wrote {args.out}")
    _, headline, moves = scenarios[0]
    print(f"  actual:  {_rank_text(baseline[athlete.plate])}")
    print(f"  what-if: {_rank_text(headline[athlete.plate])}")
    for move in moves:
        print(
            f"  {move.label}: {move.time} -> {format_seconds(move.projected_seconds)}"
            f" = {move.new_place}/{move.new_finishers + 1}, {move.new_points} pts"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
