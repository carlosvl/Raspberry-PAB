"""Local kiosk control routes."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.routes.schedule import require_admin_pin

router = APIRouter(prefix="/api/kiosk", tags=["kiosk"])

SERVICE_NAME = "raspberry-pab"


def _require_local_client(request: Request) -> None:
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kiosk controls are only available locally",
        )


def _keyboard_script() -> Path:
    return Path(__file__).resolve().parents[3] / "scripts" / "touch-keyboard.sh"


def _reload_display_script() -> Path:
    installed = Path.home() / "bin" / "reload-kiosk-display.sh"
    if installed.is_file():
        return installed
    return Path(__file__).resolve().parents[3] / "scripts" / "reload-kiosk-display.sh"


@router.post("/exit-browser")
def exit_browser(request: Request) -> dict[str, bool]:
    """Close the fullscreen Chromium kiosk browser on the local Pi."""
    _require_local_client(request)
    subprocess.Popen(
        ["sh", "-c", "pkill chromium || pkill chromium-browser || true"],
        start_new_session=True,
    )
    return {"closing": True}


@router.post("/keyboard")
def open_keyboard(request: Request) -> dict[str, bool]:
    """Open the local desktop on-screen keyboard for touchscreen input."""
    _require_local_client(request)
    script = _keyboard_script()
    if not script.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Touch keyboard launcher is not installed",
        )
    subprocess.Popen(["bash", str(script)], start_new_session=True)
    return {"opening": True}


@router.post("/restart-service", dependencies=[Depends(require_admin_pin)])
def restart_service() -> dict[str, bool]:
    """Restart the Raspberry-PAB systemd service."""
    subprocess.Popen(
        ["sudo", "-n", "systemctl", "restart", SERVICE_NAME],
        start_new_session=True,
    )
    return {"restarting": True}


@router.post("/reload-display", dependencies=[Depends(require_admin_pin)])
def reload_display() -> dict[str, bool]:
    """Hard-reload the HDMI kiosk Chromium window (local or remote admin)."""
    script = _reload_display_script()
    if not script.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Kiosk reload script is not installed",
        )
    subprocess.Popen(["bash", str(script)], start_new_session=True)
    return {"reloading": True}
