"""Local kiosk control routes."""

from __future__ import annotations

import subprocess

from fastapi import APIRouter

router = APIRouter(prefix="/api/kiosk", tags=["kiosk"])


@router.post("/exit-browser")
def exit_browser() -> dict[str, bool]:
    """Close the fullscreen Chromium kiosk browser on the local Pi."""
    subprocess.Popen(
        ["sh", "-c", "pkill chromium || pkill chromium-browser || true"],
        start_new_session=True,
    )
    return {"closing": True}
