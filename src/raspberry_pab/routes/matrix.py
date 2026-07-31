"""Admin routes for testing the Arduino WS2812 matrix."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.arduino_serial import effective_matrix_port
from raspberry_pab.matrix_controller import MatrixController
from raspberry_pab.models import LedStripTest
from raspberry_pab.routes.schedule import get_settings, require_admin_pin

router = APIRouter(prefix="/api", tags=["matrix"])


def get_matrix_controller(request: Request) -> MatrixController:
    return cast(MatrixController, request.app.state.matrix_controller)


@router.post(
    "/admin/matrix/test",
    dependencies=[Depends(require_admin_pin)],
)
async def test_matrix(request: Request, body: LedStripTest) -> dict[str, bool]:
    settings = get_settings(request)
    if not settings.matrix_enabled or not effective_matrix_port(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Matrix is not configured on this kiosk",
        )
    controller = get_matrix_controller(request)
    await controller.flash_test(
        led_red=body.led_red,
        led_green=body.led_green,
        led_blue=body.led_blue,
        led_flash_interval_ms=body.led_flash_interval_ms,
        led_flash_duration_seconds=body.led_flash_duration_seconds,
        led_chase_duration_seconds=body.led_chase_duration_seconds,
        message=body.message,
    )
    return {"testing": True}
