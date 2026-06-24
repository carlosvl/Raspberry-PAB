"""Tests for BLE LED controller behavior."""

from __future__ import annotations

import asyncio
from typing import Any

from raspberry_pab.config import Settings
from raspberry_pab.led_controller import LedController
from raspberry_pab.models import ReminderRule


class MockLamp:
    def __init__(self) -> None:
        self.connected = False
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def connect(self) -> None:
        self.connected = True
        self.calls.append(("connect", ()))

    async def disconnect(self) -> None:
        self.connected = False
        self.calls.append(("disconnect", ()))

    async def set_rgb(self, red: int, green: int, blue: int) -> None:
        self.calls.append(("set_rgb", (red, green, blue)))

    async def set_animation(self, mode: int) -> None:
        self.calls.append(("set_animation", (mode,)))

    async def set_speed(self, speed: int) -> None:
        self.calls.append(("set_speed", (speed,)))

    async def power_on(self) -> None:
        self.calls.append(("power_on", ()))

    async def power_off(self) -> None:
        self.calls.append(("power_off", ()))


def _enabled_rule(**overrides: object) -> ReminderRule:
    values: dict[str, object] = {
        "id": 1,
        "offset_minutes": 30,
        "message_template": "Warm Up {name}",
        "led_enabled": True,
        "led_red": 255,
        "led_green": 200,
        "led_blue": 0,
        "led_flash_interval_ms": 200,
        "led_flash_duration_seconds": 1,
        "led_chase_duration_seconds": 0,
    }
    values.update(overrides)
    return ReminderRule(**values)  # type: ignore[arg-type]


def test_flash_skips_when_globally_disabled() -> None:
    async def run() -> None:
        lamp = MockLamp()

        async def factory(_settings: Settings) -> MockLamp:
            return lamp

        controller = LedController(
            Settings(led_enabled=False, led_address="BE:28:79:00:06:CB"),
            lamp_factory=factory,
        )
        await controller.flash(_enabled_rule())
        await controller.shutdown()
        assert lamp.calls == []

    asyncio.run(run())


def test_flash_skips_when_rule_led_disabled() -> None:
    async def run() -> None:
        lamp = MockLamp()

        async def factory(_settings: Settings) -> MockLamp:
            return lamp

        controller = LedController(
            Settings(led_enabled=True, led_address="BE:28:79:00:06:CB"),
            lamp_factory=factory,
        )
        await controller.flash(_enabled_rule(led_enabled=False))
        await controller.shutdown()
        assert lamp.calls == []

    asyncio.run(run())


async def _wait_for_flash(controller: LedController) -> None:
    if controller._flash_task is not None:
        await controller._flash_task


def test_flash_runs_connect_and_disconnect() -> None:
    async def run() -> None:
        lamp = MockLamp()

        async def factory(_settings: Settings) -> MockLamp:
            return lamp

        controller = LedController(
            Settings(led_enabled=True, led_address="BE:28:79:00:06:CB"),
            lamp_factory=factory,
        )
        await controller.flash(_enabled_rule())
        await _wait_for_flash(controller)
        await controller.shutdown()
        assert lamp.calls[0] == ("connect", ())
        assert ("power_on", ()) in lamp.calls
        assert lamp.calls[-2] == ("power_off", ())
        assert lamp.calls[-1] == ("disconnect", ())
        assert any(call[0] == "set_rgb" for call in lamp.calls)

    asyncio.run(run())


def test_new_flash_cancels_previous() -> None:
    async def run() -> None:
        lamps: list[MockLamp] = []

        async def factory(_settings: Settings) -> MockLamp:
            lamp = MockLamp()
            lamps.append(lamp)
            return lamp

        controller = LedController(
            Settings(led_enabled=True, led_address="BE:28:79:00:06:CB"),
            lamp_factory=factory,
        )
        slow_rule = _enabled_rule(led_flash_duration_seconds=5)
        fast_rule = _enabled_rule(id=2, led_flash_duration_seconds=1)

        await controller.flash(slow_rule)
        await asyncio.sleep(0.05)
        await controller.flash(fast_rule)
        await controller.shutdown()

        assert len(lamps) >= 1

    asyncio.run(run())


def test_chase_runs_after_flash() -> None:
    async def run() -> None:
        lamp = MockLamp()

        async def factory(_settings: Settings) -> MockLamp:
            return lamp

        controller = LedController(
            Settings(led_enabled=True, led_address="BE:28:79:00:06:CB"),
            lamp_factory=factory,
        )
        await controller.flash(
            _enabled_rule(
                led_flash_interval_ms=100,
                led_flash_duration_seconds=1,
                led_chase_duration_seconds=4,
            )
        )
        await _wait_for_flash(controller)
        await controller.shutdown()
        animation_calls = [call for call in lamp.calls if call[0] == "set_animation"]
        assert len(animation_calls) >= 2
        assert animation_calls[0][1][0] != animation_calls[1][1][0]

    asyncio.run(run())
