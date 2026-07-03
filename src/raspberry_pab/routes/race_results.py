"""Race results sync and lookup routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from raspberry_pab.models import (
    ManualRaceResultLink,
    ParticipantResultMatchRecord,
    RaceEvent,
    RaceResult,
    RaceResultsSyncSummary,
)
from raspberry_pab.race_results.sync import RaceResultsSync
from raspberry_pab.routes.schedule import get_store, require_admin_pin

router = APIRouter(prefix="/api", tags=["race-results"])


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
