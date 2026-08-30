"""Admin routes for setting the Pi OS system clock."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.kiosk_clock import clear_simulated_clock, is_simulated
from raspberry_pab.models import SystemClockState, SystemClockUpdate
from raspberry_pab.routes.schedule import get_store, require_admin_pin

router = APIRouter(prefix="/api/admin/system-clock", tags=["system-clock"])


def _set_time_script() -> Path:
    installed = Path.home() / "bin" / "set-pi-system-time.sh"
    if installed.is_file():
        return installed
    return Path(__file__).resolve().parents[3] / "scripts" / "set-pi-system-time.sh"


def _run_script(args: list[str], *, use_sudo: bool = True) -> dict[str, object]:
    script = _set_time_script()
    if not script.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System clock script is not installed",
        )
    command = [str(script), *args]
    if use_sudo:
        command = ["sudo", "-n", *command]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timed out setting system clock",
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "Failed to set system clock").strip()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        ) from exc
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid response from system clock script",
        ) from exc


def _to_state(payload: dict[str, object], *, simulated: bool) -> SystemClockState:
    return SystemClockState(
        local_time=str(payload.get("local_time", "")),
        timezone=str(payload.get("timezone", "")),
        ntp=bool(payload.get("ntp", False)),
        ntp_raw=str(payload.get("ntp_raw", "")),
        simulated_kiosk=simulated,
        persists_offline=bool(payload.get("persists_offline", False)),
        fake_hwclock_saved=(
            str(payload["fake_hwclock_saved"])
            if payload.get("fake_hwclock_saved") not in (None, "")
            else None
        ),
    )


@router.get("", response_model=SystemClockState, dependencies=[Depends(require_admin_pin)])
def get_system_clock(request: Request) -> SystemClockState:
    store = get_store(request)
    payload = _run_script(["status", "--json"], use_sudo=False)
    return _to_state(payload, simulated=is_simulated(store))


@router.put("", response_model=SystemClockState, dependencies=[Depends(require_admin_pin)])
def set_system_clock(request: Request, body: SystemClockUpdate) -> SystemClockState:
    store = get_store(request)
    try:
        when = datetime(
            body.year,
            body.month,
            body.day,
            body.hour,
            body.minute,
            body.second,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date/time: {exc}",
        ) from exc

    payload = _run_script(
        ["set", when.strftime("%Y-%m-%d %H:%M:%S")],
        use_sudo=True,
    )
    # Real OS clock wins for events; drop any Test Lab simulation.
    clear_simulated_clock(store)
    return _to_state(payload, simulated=False)
