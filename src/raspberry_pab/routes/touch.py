"""Admin routes for touch trackpad tuning."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from raspberry_pab.models import TouchConfigResponse, TouchConfigUpdate
from raspberry_pab.routes.schedule import require_admin_pin
from raspberry_pab.touch_config import save_touch_config, touch_response

router = APIRouter(prefix="/api", tags=["touch"])


def _apply_script() -> Path:
    fast = Path.home() / "bin" / "apply-input-config.sh"
    if fast.is_file():
        return fast
    return Path.home() / "bin" / "setup-touch-input.sh"


def _apply_touch_config() -> None:
    script = _apply_script()
    if not script.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Input apply script is not installed",
        )
    subprocess.Popen(["bash", str(script)], start_new_session=True)


@router.get(
    "/admin/touch",
    response_model=TouchConfigResponse,
    dependencies=[Depends(require_admin_pin)],
)
def get_touch_config() -> TouchConfigResponse:
    return TouchConfigResponse(**touch_response())


@router.put(
    "/admin/touch",
    response_model=TouchConfigResponse,
    dependencies=[Depends(require_admin_pin)],
)
def update_touch_config(update: TouchConfigUpdate) -> TouchConfigResponse:
    if update.drag_start <= update.tap_slop:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Drag start must be greater than tap slop",
        )
    save_touch_config(
        {
            "PAB_TOUCH_TAP_SLOP": str(update.tap_slop),
            "PAB_TOUCH_DRAG_START": str(update.drag_start),
            "PAB_TOUCH_MULTI_TAP_SECONDS": str(update.multi_tap_seconds),
            "PAB_TOUCH_SENS": str(update.sensitivity),
            "PAB_GAMEPAD_ENABLED": "1" if update.gamepad_enabled else "0",
            "PAB_GAMEPAD_SENS": str(update.gamepad_sensitivity),
            "PAB_GAMEPAD_DEADZONE": str(update.gamepad_deadzone),
            "PAB_GAMEPAD_EDGE_MARGIN": str(update.gamepad_edge_margin),
            "PAB_GAMEPAD_SCROLL_SENS": str(update.gamepad_scroll_sensitivity),
        }
    )
    _apply_touch_config()
    return TouchConfigResponse(**touch_response())
