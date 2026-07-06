"""Admin routes for testing the BLE LED strip."""

from __future__ import annotations

import asyncio
import logging
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.config import Settings
from raspberry_pab.led_controller import LedController
from raspberry_pab.models import LedStripTest
from raspberry_pab.routes.schedule import get_settings, require_admin_pin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["led"])


def get_led_controller(request: Request) -> LedController:
    return cast(LedController, request.app.state.led_controller)


@router.post(
    "/admin/led/test",
    dependencies=[Depends(require_admin_pin)],
)
async def test_led_strip(request: Request, body: LedStripTest) -> dict[str, object]:
    settings = get_settings(request)
    if not settings.led_enabled or not settings.led_address:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"LED strip is not configured. "
                f"led_enabled={settings.led_enabled}, "
                f"led_address={settings.led_address!r}"
            ),
        )
    controller = get_led_controller(request)
    total_seconds = body.led_flash_duration_seconds + (body.led_chase_duration_seconds or 0)
    timeout = max(total_seconds + 15, 30)  # BLE connect + flash + buffer
    try:
        async with asyncio.timeout(timeout):
            await controller.flash_test_sync(
                led_red=body.led_red,
                led_green=body.led_green,
                led_blue=body.led_blue,
                led_flash_interval_ms=body.led_flash_interval_ms,
                led_flash_duration_seconds=body.led_flash_duration_seconds,
                led_chase_duration_seconds=body.led_chase_duration_seconds,
            )
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"LED test timed out after {timeout}s — BLE device may be unreachable",
        )
    except Exception as exc:
        logger.exception("LED test failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LED test failed: {exc}",
        ) from exc
    return {"testing": True, "address": settings.led_address}
