"""Admin routes for testing the Arduino buzzer."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.buzzer_controller import BuzzerController
from raspberry_pab.models import BuzzerTest
from raspberry_pab.routes.schedule import get_settings, require_admin_pin

router = APIRouter(prefix="/api", tags=["buzzer"])


def get_buzzer_controller(request: Request) -> BuzzerController:
    return cast(BuzzerController, request.app.state.buzzer_controller)


@router.post(
    "/admin/buzzer/test",
    dependencies=[Depends(require_admin_pin)],
)
async def test_buzzer(request: Request, body: BuzzerTest) -> dict[str, bool]:
    settings = get_settings(request)
    if not settings.buzzer_enabled or not settings.buzzer_port:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Buzzer is not configured on this kiosk",
        )
    controller = get_buzzer_controller(request)
    await controller.beep_test(
        buzzer_pitch_hz=body.buzzer_pitch_hz,
        buzzer_volume=body.buzzer_volume,
        buzzer_count=body.buzzer_count,
        buzzer_beep_ms=body.buzzer_beep_ms,
        buzzer_gap_ms=body.buzzer_gap_ms,
    )
    return {"testing": True}
