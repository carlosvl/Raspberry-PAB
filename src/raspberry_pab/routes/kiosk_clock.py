"""Admin routes for simulated kiosk clock."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from raspberry_pab.kiosk_clock import (
    clear_simulated_clock,
    get_clock_state,
    set_simulated_now,
)
from raspberry_pab.models import KioskClockState, KioskClockUpdate
from raspberry_pab.routes.schedule import get_store, require_admin_pin

router = APIRouter(prefix="/api", tags=["kiosk-clock"])


@router.get(
    "/admin/kiosk-clock",
    response_model=KioskClockState,
    dependencies=[Depends(require_admin_pin)],
)
def read_kiosk_clock(request: Request) -> KioskClockState:
    return KioskClockState.model_validate(get_clock_state(get_store(request)))


@router.put(
    "/admin/kiosk-clock",
    response_model=KioskClockState,
    dependencies=[Depends(require_admin_pin)],
)
def update_kiosk_clock(request: Request, body: KioskClockUpdate) -> KioskClockState:
    store = get_store(request)
    set_simulated_now(store, when=body.simulated_now, running=body.running)
    return KioskClockState.model_validate(get_clock_state(store))


@router.delete(
    "/admin/kiosk-clock",
    response_model=KioskClockState,
    dependencies=[Depends(require_admin_pin)],
)
def reset_kiosk_clock(request: Request) -> KioskClockState:
    store = get_store(request)
    clear_simulated_clock(store)
    return KioskClockState.model_validate(get_clock_state(store))
