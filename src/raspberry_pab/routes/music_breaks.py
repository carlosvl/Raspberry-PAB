"""Admin routes for interval music breaks."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.models import MusicBreakConfig, MusicBreakConfigUpdate, MusicBreakStatus
from raspberry_pab.music_break_scheduler import MusicBreakScheduler
from raspberry_pab.music_breaks import parse_start_time, save_config
from raspberry_pab.routes.schedule import get_store, require_admin_pin

router = APIRouter(prefix="/api", tags=["music-breaks"])


def get_music_break_scheduler(request: Request) -> MusicBreakScheduler:
    return cast(MusicBreakScheduler, request.app.state.music_break_scheduler)


def _status_response(request: Request) -> MusicBreakStatus:
    scheduler = get_music_break_scheduler(request)
    fields = scheduler.status_fields()
    return MusicBreakStatus.model_validate(fields)


@router.get(
    "/admin/music-breaks",
    response_model=MusicBreakStatus,
    dependencies=[Depends(require_admin_pin)],
)
def get_music_breaks(request: Request) -> MusicBreakStatus:
    return _status_response(request)


@router.put(
    "/admin/music-breaks",
    response_model=MusicBreakStatus,
    dependencies=[Depends(require_admin_pin)],
)
def put_music_breaks(
    request: Request,
    body: MusicBreakConfigUpdate,
) -> MusicBreakStatus:
    try:
        parse_start_time(body.start_time)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    store = get_store(request)
    known = {sound.id for sound in store.list_sounds()}
    missing = [sound_id for sound_id in body.sound_ids if sound_id not in known]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown sound ids: {missing}",
        )
    config = MusicBreakConfig.model_validate(body.model_dump())
    save_config(store, config)
    return _status_response(request)


@router.post(
    "/admin/music-breaks/test",
    response_model=MusicBreakStatus,
    dependencies=[Depends(require_admin_pin)],
)
async def test_music_breaks(request: Request) -> MusicBreakStatus:
    scheduler = get_music_break_scheduler(request)
    try:
        await scheduler.run_test(duration_seconds=10.0)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _status_response(request)


@router.post(
    "/admin/music-breaks/stop",
    response_model=MusicBreakStatus,
    dependencies=[Depends(require_admin_pin)],
)
async def stop_music_breaks(request: Request) -> MusicBreakStatus:
    scheduler = get_music_break_scheduler(request)
    await scheduler.interrupt()
    return _status_response(request)
