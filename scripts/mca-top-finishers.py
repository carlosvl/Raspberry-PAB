#!/usr/bin/env python3
"""Top finishers per HS category: State Championship race and season standings."""

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
from raspberry_pab.race_results.series_fetch import fetch_series_sessions  # noqa: E402
from raspberry_pab.race_results.top_finishers import (  # noqa: E402
    bibs_from_sessions,
    render_lists,
    top_race,
    top_season,
)


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
    parser.set_defaults(out=_REPO_ROOT / "docs" / "mca-top-finishers.md")
    parser.add_argument("--top", type=int, default=15, help="Riders per category")
    parser.add_argument(
        "--race-id",
        default="17339",
        help="IYR series id of the race to rank (default: State, Redhead)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.race_id not in args.state_event:
        args.state_event.append(args.race_id)  # keep this race out of the season
    if not args.canceled:
        args.canceled.append("17333:HS")  # Theodore Wirth HS day canceled 9/27
    client = RaceResultsClient()
    season = QUAL.load_season(args, client)
    if season is None:
        return 1

    url = f"https://www.itsyourrace.com/results.aspx?id={args.race_id}"
    race = fetch_series_sessions(url)
    status = sorted({s.results_status for s in race.sessions})
    bibs = bibs_from_sessions(race.sessions)

    lines = [
        "# MCA top finishers by category",
        "",
        f"- **Generated:** {datetime.now(UTC).astimezone().isoformat(timespec='minutes')}",
        f"- **Race results:** [ITS YOUR RACE {args.race_id}]({url}) — "
        f"{'; '.join(status) or 'no results'} (preliminary until MCA posts the PDF)",
        "- **Season standings:** "
        + "; ".join(
            f"[{d.title}]({d.url}) through Race {t.through_race}"
            for d, t in zip(season.standings_docs, season.tables, strict=True)
        ),
        f"- **Scope:** Freshman, JV2, JV3, Varsity (HS), top {args.top}. D1/D2 "
        "stay separate where MCA splits them. DNFs are excluded. Senior Open and "
        "middle school are not listed.",
        "- **Team contact:** the team site and the team address MCA publishes in "
        "its [Team Finder](https://minnesotacycling.org/team-finder-2/); contact "
        "the coach, not riders. Schools without a confident match link to the "
        "Team Finder.",
        "- **Find:** the Strava link opens Strava's athlete search (login "
        "required); the Google link searches name + school. Neither is a "
        "confirmed match, so check the school and age before relying on a profile.",
        "",
    ]
    race_lists = top_race(race.sessions, args.top)
    season_lists = top_season(season.riders, args.top, bibs=bibs)
    lines += render_lists("State race finishers", race_lists)
    lines += render_lists("Season standings", season_lists)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.out}: {len(race_lists)} race lists, "
        f"{len(season_lists)} season lists"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
