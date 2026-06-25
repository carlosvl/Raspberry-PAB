"""Admin routes for touch trackpad tuning."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.models import TouchConfigResponse, TouchConfigUpdate
from raspberry_pab.routes.schedule import require_admin_pin
from raspberry_pab.touch_config import save_touch_config, touch_response

router = APIRouter(prefix="/api", tags=["touch"])


def _setup_script() -> Path:
    return Path.home() / "bin" / "setup-touch-input.sh"


def _require_local_client(request: Request) -> None:
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Touch controls are only available locally",
        )


def _apply_touch_config() -> None:
    script = _setup_script()
    if not script.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Touch setup script is not installed",
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
def update_touch_config(request: Request, update: TouchConfigUpdate) -> TouchConfigResponse:
    _require_local_client(request)
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
        }
    )
    _apply_touch_config()
    return TouchConfigResponse(**touch_response())
