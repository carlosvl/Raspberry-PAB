"""Admin routes for testing the BLE LED strip."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.config import Settings
from raspberry_pab.led_controller import LedController
from raspberry_pab.models import LedStripTest
from raspberry_pab.routes.schedule import get_settings, require_admin_pin

router = APIRouter(prefix="/api", tags=["led"])


def get_led_controller(request: Request) -> LedController:
    return cast(LedController, request.app.state.led_controller)


@router.post(
    "/admin/led/test",
    dependencies=[Depends(require_admin_pin)],
)
async def test_led_strip(request: Request, body: LedStripTest) -> dict[str, bool]:
    settings = get_settings(request)
    if not settings.led_enabled or not settings.led_address:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LED strip is not configured on this kiosk",
        )
    controller = get_led_controller(request)
    await controller.flash_test(
        led_red=body.led_red,
        led_green=body.led_green,
        led_blue=body.led_blue,
        led_flash_interval_ms=body.led_flash_interval_ms,
        led_flash_duration_seconds=body.led_flash_duration_seconds,
        led_chase_duration_seconds=body.led_chase_duration_seconds,
    )
    return {"testing": True}
