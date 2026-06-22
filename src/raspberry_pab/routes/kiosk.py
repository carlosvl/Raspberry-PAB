"""Local kiosk control routes."""

from __future__ import annotations

import subprocess

from fastapi import APIRouter, HTTPException, Request, status

router = APIRouter(prefix="/api/kiosk", tags=["kiosk"])


@router.post("/exit-browser")
def exit_browser(request: Request) -> dict[str, bool]:
    """Close the fullscreen Chromium kiosk browser on the local Pi."""
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kiosk browser controls are only available locally",
        )
    subprocess.Popen(
        ["sh", "-c", "pkill chromium || pkill chromium-browser || true"],
        start_new_session=True,
    )
    return {"closing": True}
