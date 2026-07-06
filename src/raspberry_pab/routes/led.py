"""Admin routes for BLE LED strip configuration and testing."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.led_controller import LedController
from raspberry_pab.models import LedConfig, LedStripTest
from raspberry_pab.routes.schedule import get_settings, get_store, require_admin_pin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["led"])

LED_ENABLED_KEY = "led_enabled"
LED_ADDRESS_KEY = "led_address"
LED_NAME_KEY = "led_name"


def get_led_controller(request: Request) -> LedController:
    return cast(LedController, request.app.state.led_controller)


def _effective_led_config(settings: Settings, store: ScheduleStore) -> LedConfig:
    """Read LED config from app_settings DB, falling back to env-var settings."""
    db_enabled = store.get_setting(LED_ENABLED_KEY)
    db_address = store.get_setting(LED_ADDRESS_KEY)
    db_name = store.get_setting(LED_NAME_KEY)
    return LedConfig(
        led_enabled=(
            db_enabled.lower() in {"1", "true", "yes"}
            if db_enabled is not None
            else settings.led_enabled
        ),
        led_address=db_address if db_address is not None else settings.led_address,
        led_name=db_name if db_name is not None else settings.led_name,
    )


def _apply_led_config_to_settings(
    request: Request, config: LedConfig
) -> None:
    """Update the in-memory Settings with new LED values.

    Settings is a frozen dataclass, so we replace it on app.state.
    """
    old = get_settings(request)
    new = dataclasses.replace(
        old,
        led_enabled=config.led_enabled,
        led_address=config.led_address,
        led_name=config.led_name,
    )
    request.app.state.settings = new


# ── Config ──────────────────────────────────────────────────────────


@router.get(
    "/admin/led/config",
    dependencies=[Depends(require_admin_pin)],
)
def get_led_config(request: Request) -> dict[str, object]:
    settings = get_settings(request)
    store = get_store(request)
    config = _effective_led_config(settings, store)
    return {
        "led_enabled": config.led_enabled,
        "led_address": config.led_address,
        "led_name": config.led_name,
    }


@router.put(
    "/admin/led/config",
    dependencies=[Depends(require_admin_pin)],
)
def save_led_config(request: Request, body: LedConfig) -> dict[str, object]:
    store = get_store(request)
    store.set_setting(LED_ENABLED_KEY, str(body.led_enabled).lower())
    store.set_setting(LED_ADDRESS_KEY, body.led_address)
    store.set_setting(LED_NAME_KEY, body.led_name)
    _apply_led_config_to_settings(request, body)
    return {
        "led_enabled": body.led_enabled,
        "led_address": body.led_address,
        "led_name": body.led_name,
    }


# ── BLE Scan ────────────────────────────────────────────────────────


@router.post(
    "/admin/led/scan",
    dependencies=[Depends(require_admin_pin)],
)
async def scan_ble_devices() -> list[dict[str, str]]:
    """Discover nearby BLE devices (10s scan). Returns name + address."""
    try:
        from bleak import BleakScanner  # type: ignore[import-untyped]
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BLE scanning not available — bleak not installed",
        )
    try:
        async with asyncio.timeout(20):
            devices = await BleakScanner.discover(timeout=10)
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="BLE scan timed out",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"BLE scan failed: {exc}",
        ) from exc
    # Return only devices with a name (filters out anonymous beacons)
    return [
        {"address": d.address, "name": d.name or ""}
        for d in sorted(devices, key=lambda d: d.name or "")
        if d.name
    ]


# ── Test ────────────────────────────────────────────────────────────


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
