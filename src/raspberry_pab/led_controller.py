"""BLE LED strip control for reminder alerts."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, cast

from raspberry_pab.config import Settings
from raspberry_pab.models import ReminderRule

logger = logging.getLogger(__name__)

LampFactory = Callable[[Settings], Awaitable[Any]]

CHASE_SWAP_SECONDS = 2.0
DEFAULT_CHASE_SPEED = 50


class _LampProtocol(Protocol):
    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def power_on(self) -> None: ...

    async def set_rgb(self, red: int, green: int, blue: int) -> None: ...

    async def set_animation(self, mode: int) -> None: ...

    async def set_speed(self, speed: int) -> None: ...

    async def power_off(self) -> None: ...


async def _default_lamp_factory(settings: Settings) -> _LampProtocol:
    from lotus_lamp import DeviceConfig, LotusLamp  # type: ignore[import-untyped]

    return cast(
        _LampProtocol,
        LotusLamp(
            device_config=DeviceConfig(
                name=settings.led_name,
                address=settings.led_address,
            )
        ),
    )


def _chase_modes() -> tuple[int, int]:
    from lotus_lamp.modes import get_mode_by_category_index  # type: ignore[import-untyped]

    return (
        get_mode_by_category_index("run", 1),
        get_mode_by_category_index("runback", 1),
    )


class LedController:
    """Flashes a Lotus Lamp / MELK BLE strip when reminder rules fire."""

    def __init__(
        self,
        settings: Settings,
        *,
        lamp_factory: LampFactory | None = None,
    ) -> None:
        self._settings = settings
        self._lamp_factory = lamp_factory or _default_lamp_factory
        self._lock = asyncio.Lock()
        self._flash_task: asyncio.Task[None] | None = None

    async def flash(self, rule: ReminderRule) -> None:
        if not self._should_flash(rule):
            return
        await self._start_flash(rule)

    async def flash_test(
        self,
        *,
        led_red: int,
        led_green: int,
        led_blue: int,
        led_flash_interval_ms: int,
        led_flash_duration_seconds: int,
        led_chase_duration_seconds: int = 10,
    ) -> None:
        if not self._settings.led_enabled or not self._settings.led_address:
            return
        rule = ReminderRule(
            id=0,
            offset_minutes=0,
            message_template="LED test",
            led_enabled=True,
            led_red=led_red,
            led_green=led_green,
            led_blue=led_blue,
            led_flash_interval_ms=led_flash_interval_ms,
            led_flash_duration_seconds=led_flash_duration_seconds,
            led_chase_duration_seconds=led_chase_duration_seconds,
        )
        await self._start_flash(rule)

    async def flash_test_sync(
        self,
        *,
        led_red: int,
        led_green: int,
        led_blue: int,
        led_flash_interval_ms: int,
        led_flash_duration_seconds: int,
        led_chase_duration_seconds: int = 10,
    ) -> None:
        """Run flash directly (not in background) so errors propagate."""
        if not self._settings.led_enabled or not self._settings.led_address:
            return
        rule = ReminderRule(
            id=0,
            offset_minutes=0,
            message_template="LED test",
            led_enabled=True,
            led_red=led_red,
            led_green=led_green,
            led_blue=led_blue,
            led_flash_interval_ms=led_flash_interval_ms,
            led_flash_duration_seconds=led_flash_duration_seconds,
            led_chase_duration_seconds=led_chase_duration_seconds,
        )
        # Cancel any existing flash then run synchronously
        if self._flash_task and not self._flash_task.done():
            self._flash_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flash_task
        # Run directly — exceptions propagate to caller
        async with self._lock:
            lamp: _LampProtocol | None = None
            try:
                lamp = await self._lamp_factory(self._settings)
                await lamp.connect()
                logger.info(
                    "LED test connected to %s (%s)",
                    self._settings.led_name,
                    self._settings.led_address,
                )
                await self._run_flash_pulse(lamp, rule)
                await self._run_chase(lamp, rule)
            finally:
                if lamp is not None:
                    with contextlib.suppress(Exception):
                        await lamp.power_off()
                    with contextlib.suppress(Exception):
                        await lamp.disconnect()

    async def _start_flash(self, rule: ReminderRule) -> None:
        if self._flash_task and not self._flash_task.done():
            self._flash_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flash_task
        self._flash_task = asyncio.create_task(
            self._run_flash(rule),
            name="led-flash",
        )

    async def shutdown(self) -> None:
        if self._flash_task and not self._flash_task.done():
            self._flash_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flash_task
        self._flash_task = None

    def _should_flash(self, rule: ReminderRule) -> bool:
        return (
            self._settings.led_enabled
            and bool(self._settings.led_address)
            and rule.led_enabled
        )

    async def _run_flash_pulse(self, lamp: _LampProtocol, rule: ReminderRule) -> None:
        half_interval = rule.led_flash_interval_ms / 2000
        deadline = time.monotonic() + rule.led_flash_duration_seconds
        while time.monotonic() < deadline:
            await lamp.power_on()
            await lamp.set_rgb(rule.led_red, rule.led_green, rule.led_blue)
            await asyncio.sleep(half_interval)
            if time.monotonic() >= deadline:
                break
            await lamp.power_off()
            await asyncio.sleep(half_interval)

    async def _run_chase(self, lamp: _LampProtocol, rule: ReminderRule) -> None:
        if rule.led_chase_duration_seconds <= 0:
            return

        run_mode, runback_mode = _chase_modes()
        await lamp.power_on()
        await lamp.set_rgb(rule.led_red, rule.led_green, rule.led_blue)
        await lamp.set_speed(DEFAULT_CHASE_SPEED)

        deadline = time.monotonic() + rule.led_chase_duration_seconds
        forward = True
        while time.monotonic() < deadline:
            await lamp.set_animation(run_mode if forward else runback_mode)
            forward = not forward
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(min(CHASE_SWAP_SECONDS, remaining))

    async def _run_flash(self, rule: ReminderRule) -> None:
        async with self._lock:
            lamp: _LampProtocol | None = None
            try:
                lamp = await self._lamp_factory(self._settings)
                await lamp.connect()
                await self._run_flash_pulse(lamp, rule)
                await self._run_chase(lamp, rule)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("LED flash failed for rule %s", rule.id)
            finally:
                if lamp is not None:
                    with contextlib.suppress(Exception):
                        await lamp.power_off()
                    with contextlib.suppress(Exception):
                        await lamp.disconnect()
