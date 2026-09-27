"""Race results sync and lookup routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from raspberry_pab.kiosk_clock import effective_now
from raspberry_pab.models import (
    ManualRaceResultLink,
    ParticipantResultMatchRecord,
    RaceEvent,
    RaceResult,
    RaceResultsSyncConfig,
    RaceResultsSyncConfigUpdate,
    RaceResultsSyncSummary,
    TeamStandingBucketView,
    TeamStandingsConfig,
    TeamStandingsConfigUpdate,
    TeamStandingsSnapshot,
    TeamStandingTopEntry,
)
from raspberry_pab.race_results.sync import RaceResultsSync
from raspberry_pab.race_results.team_standings_live import (
    DEFAULT_INTERVAL_MINUTES,
    DEFAULT_SERIES_URL,
    DEFAULT_TEAM,
    SETTING_ENABLED,
    SETTING_INTERVAL,
    SETTING_SERIES_URL,
    SETTING_TEAM,
    LiveStandingsSnapshot,
    read_enabled,
    read_series_url,
    read_team,
)
from raspberry_pab.race_results.team_standings_live import (
    read_interval_minutes as read_team_interval,
)
from raspberry_pab.race_results.team_standings_scheduler import TeamStandingsScheduler
from raspberry_pab.race_results.window import (
    DEFAULT_RESULTS_SYNC_MINUTES,
    DEFAULT_RESULTS_SYNC_WINDOW_HOURS,
    RESULTS_SYNC_INTERVAL_KEY,
    RESULTS_SYNC_WINDOW_HOURS_KEY,
    read_interval_minutes,
    read_window_hours,
    results_sync_window,
)
from raspberry_pab.routes.schedule import get_store, require_admin_pin

router = APIRouter(prefix="/api", tags=["race-results"])


class SyncIntervalUpdate(BaseModel):
    interval_minutes: int = Field(ge=0, le=1440)


def get_sync(request: Request) -> RaceResultsSync:
    return RaceResultsSync(get_store(request))


def get_team_standings_scheduler(request: Request) -> TeamStandingsScheduler:
    return cast(TeamStandingsScheduler, request.app.state.team_standings_scheduler)


def _live_to_api(
    snapshot: LiveStandingsSnapshot | None,
    *,
    enabled: bool,
    series_url: str,
    focus_team: str,
) -> TeamStandingsSnapshot:
    if snapshot is None:
        return TeamStandingsSnapshot(
            enabled=enabled,
            series_url=series_url,
            focus_team=focus_team,
        )
    return TeamStandingsSnapshot(
        enabled=enabled,
        series_url=snapshot.series_url,
        focus_team=snapshot.focus_team,
        scraped_at=snapshot.scraped_at,
        ticker_text=snapshot.ticker_text,
        matrix_messages=list(snapshot.matrix_messages),
        buckets=[
            TeamStandingBucketView(
                race_date=bucket.race_date,
                bucket=bucket.bucket.value,
                division_label=bucket.division_label,
                focus_place=bucket.focus_place,
                focus_score=bucket.focus_score,
                focus_team=bucket.focus_team,
                top3=[
                    TeamStandingTopEntry(
                        place=entry.place,
                        team_name=entry.team_name,
                        score=entry.score,
                    )
                    for entry in bucket.top3
                ],
            )
            for bucket in snapshot.buckets
        ],
        results_status=snapshot.results_status,
        error=snapshot.error,
    )


def _team_config_response(request: Request) -> TeamStandingsConfig:
    store = get_store(request)
    scheduler = get_team_standings_scheduler(request)
    snapshot = scheduler.snapshot
    return TeamStandingsConfig(
        enabled=read_enabled(store),
        series_url=read_series_url(store),
        focus_team=read_team(store),
        interval_minutes=read_team_interval(store),
        ticker_text=snapshot.ticker_text if snapshot else "",
        scraped_at=snapshot.scraped_at if snapshot else None,
        error=snapshot.error if snapshot else None,
    )


def _sync_config_response(request: Request) -> RaceResultsSyncConfig:
    store = get_store(request)
    now = effective_now(store)
    interval = read_interval_minutes(store)
    window_hours = read_window_hours(store)
    window = results_sync_window(store, now, window_hours=window_hours)
    return RaceResultsSyncConfig(
        interval_minutes=interval,
        window_hours=window_hours,
        active=window.active and interval > 0,
        window_start=window.window_start,
        window_end=window.window_end,
        next_eligible=window.next_eligible,
        kiosk_now=now,
    )


@router.get("/race-results", response_model=list[ParticipantResultMatchRecord])
def list_race_results(
    request: Request,
    date_filter: Annotated[date | None, Query(alias="date")] = None,
) -> list[ParticipantResultMatchRecord]:
    event_date = date_filter or date.today()
    return get_store(request).list_participant_result_matches(event_date)


@router.get("/team-standings", response_model=TeamStandingsSnapshot)
def get_team_standings(request: Request) -> TeamStandingsSnapshot:
    store = get_store(request)
    scheduler = get_team_standings_scheduler(request)
    return _live_to_api(
        scheduler.snapshot,
        enabled=read_enabled(store),
        series_url=read_series_url(store),
        focus_team=read_team(store),
    )


@router.get(
    "/admin/race-events",
    response_model=list[RaceEvent],
    dependencies=[Depends(require_admin_pin)],
)
def list_race_events(request: Request) -> list[RaceEvent]:
    return get_store(request).list_race_events()


@router.post(
    "/admin/race-results/sync-index",
    response_model=list[RaceEvent],
    dependencies=[Depends(require_admin_pin)],
)
def sync_race_index(request: Request) -> list[RaceEvent]:
    sync = get_sync(request)
    try:
        return sync.sync_index()
    finally:
        sync.close()


@router.post(
    "/admin/race-results/sync-date",
    response_model=RaceResultsSyncSummary,
    dependencies=[Depends(require_admin_pin)],
)
def sync_race_results_for_date(
    request: Request,
    date_filter: Annotated[date | None, Query(alias="date")] = None,
) -> RaceResultsSyncSummary:
    event_date = date_filter or date.today()
    sync = get_sync(request)
    try:
        return sync.sync_date(event_date)
    finally:
        sync.close()


@router.get(
    "/admin/race-results",
    response_model=list[ParticipantResultMatchRecord],
    dependencies=[Depends(require_admin_pin)],
)
def admin_list_race_results(
    request: Request,
    date_filter: Annotated[date | None, Query(alias="date")] = None,
) -> list[ParticipantResultMatchRecord]:
    event_date = date_filter or date.today()
    return get_store(request).list_participant_result_matches(event_date)


@router.post(
    "/admin/race-results/link",
    response_model=RaceResult,
    dependencies=[Depends(require_admin_pin)],
)
def link_race_result_manual(
    request: Request,
    body: ManualRaceResultLink,
) -> RaceResult:
    return get_store(request).link_race_result_manual(body)


@router.get(
    "/admin/race-results/sync-config",
    response_model=RaceResultsSyncConfig,
    dependencies=[Depends(require_admin_pin)],
)
def get_sync_config(request: Request) -> RaceResultsSyncConfig:
    return _sync_config_response(request)


@router.put(
    "/admin/race-results/sync-config",
    response_model=RaceResultsSyncConfig,
    dependencies=[Depends(require_admin_pin)],
)
def set_sync_config(
    request: Request,
    body: RaceResultsSyncConfigUpdate,
) -> RaceResultsSyncConfig:
    store = get_store(request)
    if body.interval_minutes == DEFAULT_RESULTS_SYNC_MINUTES:
        store.delete_setting(RESULTS_SYNC_INTERVAL_KEY)
    else:
        store.set_setting(RESULTS_SYNC_INTERVAL_KEY, str(body.interval_minutes))
    if body.window_hours == DEFAULT_RESULTS_SYNC_WINDOW_HOURS:
        store.delete_setting(RESULTS_SYNC_WINDOW_HOURS_KEY)
    else:
        store.set_setting(RESULTS_SYNC_WINDOW_HOURS_KEY, str(body.window_hours))
    return _sync_config_response(request)


@router.get(
    "/admin/race-results/sync-interval",
    dependencies=[Depends(require_admin_pin)],
)
def get_sync_interval(request: Request) -> dict[str, int]:
    """Legacy interval-only endpoint. Prefer /sync-config."""
    return {"interval_minutes": read_interval_minutes(get_store(request))}


@router.put(
    "/admin/race-results/sync-interval",
    dependencies=[Depends(require_admin_pin)],
)
def set_sync_interval(
    request: Request,
    body: SyncIntervalUpdate,
) -> dict[str, int]:
    """Legacy interval-only endpoint. Prefer /sync-config."""
    store = get_store(request)
    if body.interval_minutes == DEFAULT_RESULTS_SYNC_MINUTES:
        store.delete_setting(RESULTS_SYNC_INTERVAL_KEY)
    else:
        store.set_setting(RESULTS_SYNC_INTERVAL_KEY, str(body.interval_minutes))
    return {"interval_minutes": read_interval_minutes(store)}


@router.get(
    "/admin/team-standings/config",
    response_model=TeamStandingsConfig,
    dependencies=[Depends(require_admin_pin)],
)
def get_team_standings_config(request: Request) -> TeamStandingsConfig:
    return _team_config_response(request)


@router.put(
    "/admin/team-standings/config",
    response_model=TeamStandingsConfig,
    dependencies=[Depends(require_admin_pin)],
)
def set_team_standings_config(
    request: Request,
    body: TeamStandingsConfigUpdate,
) -> TeamStandingsConfig:
    store = get_store(request)
    store.set_setting(SETTING_ENABLED, "true" if body.enabled else "false")
    if body.series_url.strip() == DEFAULT_SERIES_URL:
        store.delete_setting(SETTING_SERIES_URL)
    else:
        store.set_setting(SETTING_SERIES_URL, body.series_url.strip())
    if body.focus_team.strip() == DEFAULT_TEAM:
        store.delete_setting(SETTING_TEAM)
    else:
        store.set_setting(SETTING_TEAM, body.focus_team.strip())
    if body.interval_minutes == DEFAULT_INTERVAL_MINUTES:
        store.delete_setting(SETTING_INTERVAL)
    else:
        store.set_setting(SETTING_INTERVAL, str(body.interval_minutes))
    return _team_config_response(request)


@router.post(
    "/admin/team-standings/refresh",
    response_model=TeamStandingsSnapshot,
    dependencies=[Depends(require_admin_pin)],
)
async def refresh_team_standings(request: Request) -> TeamStandingsSnapshot:
    store = get_store(request)
    scheduler = get_team_standings_scheduler(request)
    snapshot = await scheduler.refresh_now()
    return _live_to_api(
        snapshot,
        enabled=read_enabled(store),
        series_url=read_series_url(store),
        focus_team=read_team(store),
    )
