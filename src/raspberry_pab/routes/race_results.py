"""Race results sync and lookup routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from raspberry_pab.models import (
    ManualRaceResultLink,
    ParticipantResultMatchRecord,
    RaceEvent,
    RaceResult,
    RaceResultsSyncSummary,
)
from raspberry_pab.race_results.sync import RaceResultsSync
from raspberry_pab.routes.schedule import get_store, require_admin_pin
from raspberry_pab.scheduler import DEFAULT_RESULTS_SYNC_MINUTES, RESULTS_SYNC_INTERVAL_KEY

router = APIRouter(prefix="/api", tags=["race-results"])


class SyncIntervalUpdate(BaseModel):
    interval_minutes: int = Field(ge=0, le=1440)


def get_sync(request: Request) -> RaceResultsSync:
    return RaceResultsSync(get_store(request))


@router.get("/race-results", response_model=list[ParticipantResultMatchRecord])
def list_race_results(
    request: Request,
    date_filter: Annotated[date | None, Query(alias="date")] = None,
) -> list[ParticipantResultMatchRecord]:
    event_date = date_filter or date.today()
    return get_store(request).list_participant_result_matches(event_date)


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
    "/admin/race-results/sync-interval",
    dependencies=[Depends(require_admin_pin)],
)
def get_sync_interval(request: Request) -> dict[str, int]:
    store = get_store(request)
    raw = store.get_setting(RESULTS_SYNC_INTERVAL_KEY)
    interval = DEFAULT_RESULTS_SYNC_MINUTES
    if raw is not None:
        try:
            val = int(raw)
            if val >= 0:
                interval = val
        except ValueError:
            pass
    return {"interval_minutes": interval}


@router.put(
    "/admin/race-results/sync-interval",
    dependencies=[Depends(require_admin_pin)],
)
def set_sync_interval(
    request: Request,
    body: SyncIntervalUpdate,
) -> dict[str, int]:
    store = get_store(request)
    if body.interval_minutes == DEFAULT_RESULTS_SYNC_MINUTES:
        store.delete_setting(RESULTS_SYNC_INTERVAL_KEY)
    else:
        store.set_setting(RESULTS_SYNC_INTERVAL_KEY, str(body.interval_minutes))
    return {"interval_minutes": body.interval_minutes}
