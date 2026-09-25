"""Live MCA team standings: scrape, score, and format ticker/matrix text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from raspberry_pab.db import ScheduleStore
from raspberry_pab.matrix_controller import sanitize_matrix_message
from raspberry_pab.race_results.client import FetchText
from raspberry_pab.race_results.mca_scoring import (
    DayStandings,
    StandingsBucket,
    TeamScore,
    build_all_standings,
    normalize_team_name,
    riders_from_sessions,
)
from raspberry_pab.race_results.series_fetch import fetch_series_sessions

DEFAULT_SERIES_URL = "https://www.itsyourrace.com/results.aspx?id=17320"
DEFAULT_TEAM = "Roseville"
DEFAULT_INTERVAL_MINUTES = 5

SETTING_ENABLED = "team_standings_enabled"
SETTING_SERIES_URL = "team_standings_series_url"
SETTING_TEAM = "team_standings_team"
SETTING_INTERVAL = "team_standings_interval_minutes"

_BUCKET_LABELS: dict[StandingsBucket, str] = {
    StandingsBucket.HS_D1: "HS D1",
    StandingsBucket.HS_D2: "HS D2",
    StandingsBucket.MS_D1: "MS D1",
    StandingsBucket.MS_D2: "MS D2",
}


@dataclass(frozen=True)
class TopTeamEntry:
    place: int
    team_name: str
    score: int


@dataclass(frozen=True)
class BucketStanding:
    race_date: date
    bucket: StandingsBucket
    division_label: str
    focus_place: int | None
    focus_score: int | None
    focus_team: str
    top3: list[TopTeamEntry]


@dataclass(frozen=True)
class LiveStandingsSnapshot:
    series_url: str
    focus_team: str
    scraped_at: datetime
    buckets: list[BucketStanding]
    ticker_text: str
    matrix_messages: list[str]
    error: str | None = None
    results_status: str | None = None


def read_enabled(store: ScheduleStore) -> bool:
    raw = store.get_setting(SETTING_ENABLED)
    if raw is None:
        # Default on when a series URL is configured (including default).
        return True
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def read_series_url(store: ScheduleStore) -> str:
    raw = store.get_setting(SETTING_SERIES_URL)
    if raw is None or not raw.strip():
        return DEFAULT_SERIES_URL
    return raw.strip()


def read_team(store: ScheduleStore) -> str:
    raw = store.get_setting(SETTING_TEAM)
    if raw is None or not raw.strip():
        return DEFAULT_TEAM
    return raw.strip()


def read_interval_minutes(store: ScheduleStore) -> int:
    raw = store.get_setting(SETTING_INTERVAL)
    if raw is None:
        return DEFAULT_INTERVAL_MINUTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_INTERVAL_MINUTES
    if value < 0:
        return DEFAULT_INTERVAL_MINUTES
    return min(value, 1440)


def abbreviate_team(name: str, *, max_len: int = 5) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", "", name).strip()
    if not cleaned:
        return "Team"
    tokens = cleaned.split()
    if len(tokens) == 1:
        return tokens[0][:max_len]
    # Prefer first letters + truncated last significant word.
    initials = "".join(t[0] for t in tokens[:-1] if t)
    last = tokens[-1][: max(2, max_len - len(initials))]
    abbr = f"{initials}{last}" if initials else last
    return abbr[:max_len]


def _find_focus(
    scores: list[TeamScore], focus_team: str
) -> tuple[int, TeamScore] | None:
    needle = normalize_team_name(focus_team)
    for index, score in enumerate(scores):
        if normalize_team_name(score.team_name) == needle:
            return index + 1, score
    return None


def buckets_from_standings(
    days: list[DayStandings],
    *,
    focus_team: str,
) -> list[BucketStanding]:
    result: list[BucketStanding] = []
    for day in days:
        for bucket in StandingsBucket:
            scores = day.buckets.get(bucket) or []
            if not scores:
                continue
            focus = _find_focus(scores, focus_team)
            top3 = [
                TopTeamEntry(
                    place=i + 1,
                    team_name=s.team_name,
                    score=s.total_points,
                )
                for i, s in enumerate(scores[:3])
            ]
            result.append(
                BucketStanding(
                    race_date=day.race_date,
                    bucket=bucket,
                    division_label=_BUCKET_LABELS[bucket],
                    focus_place=focus[0] if focus else None,
                    focus_score=focus[1].total_points if focus else None,
                    focus_team=focus_team,
                    top3=top3,
                )
            )
    return result


def format_ticker_text(buckets: list[BucketStanding]) -> str:
    parts: list[str] = []
    for bucket in buckets:
        if bucket.focus_place is None:
            top = " · ".join(
                f"{entry.team_name} {entry.score}" for entry in bucket.top3
            )
            parts.append(
                f"{bucket.division_label} ({bucket.race_date.isoformat()}): "
                f"Top 3: {top or '—'}"
            )
            continue
        top = " · ".join(f"{entry.team_name} {entry.score}" for entry in bucket.top3)
        parts.append(
            f"{bucket.division_label}: {bucket.focus_team} #{bucket.focus_place} "
            f"({bucket.focus_score}) · Top 3: {top}"
        )
    return " | ".join(parts)


def format_matrix_messages(
    buckets: list[BucketStanding],
    *,
    focus_team: str,
) -> list[str]:
    messages: list[str] = []
    focus_abbr = abbreviate_team(focus_team)
    for bucket in buckets:
        if bucket.focus_place is None:
            continue
        others = [
            abbreviate_team(entry.team_name)
            for entry in bucket.top3
            if normalize_team_name(entry.team_name) != normalize_team_name(focus_team)
        ][:2]
        suffix = f" · {' '.join(others)}" if others else ""
        raw = f"{bucket.division_label} #{bucket.focus_place} {focus_abbr}{suffix}"
        messages.append(sanitize_matrix_message(raw))
    return messages


def build_snapshot_from_standings(
    days: list[DayStandings],
    *,
    series_url: str,
    focus_team: str,
    scraped_at: datetime,
    results_status: str | None = None,
    error: str | None = None,
) -> LiveStandingsSnapshot:
    buckets = buckets_from_standings(days, focus_team=focus_team)
    return LiveStandingsSnapshot(
        series_url=series_url,
        focus_team=focus_team,
        scraped_at=scraped_at,
        buckets=buckets,
        ticker_text=format_ticker_text(buckets),
        matrix_messages=format_matrix_messages(buckets, focus_team=focus_team),
        error=error,
        results_status=results_status,
    )


def refresh_live_standings(
    *,
    series_url: str,
    focus_team: str,
    scraped_at: datetime,
    fetch_text: FetchText | None = None,
) -> LiveStandingsSnapshot:
    result = fetch_series_sessions(series_url, fetch_text=fetch_text)
    riders = riders_from_sessions(result.sessions)
    days = build_all_standings(riders)
    statuses = sorted({session.results_status for session in result.sessions})
    status = ", ".join(statuses) if statuses else None
    return build_snapshot_from_standings(
        days,
        series_url=series_url,
        focus_team=focus_team,
        scraped_at=scraped_at,
        results_status=status,
    )
