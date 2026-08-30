"""Tests for Arduino WS2812 matrix controller behavior."""

from __future__ import annotations

import asyncio

from raspberry_pab.config import Settings
from raspberry_pab.matrix_controller import (
    MatrixController,
    build_bright_command,
    build_scroll_command,
    matrix_display_duration_ms,
    sanitize_matrix_message,
)
from raspberry_pab.models import ReminderRule


class MockSerial:
    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.closed = False
        self._reads = [
            b"READY\n",
            b"PONG\n",
            b"OK\n",
            b"OK\n",
        ]

    def readline(self) -> bytes:
        if self._reads:
            return self._reads.pop(0)
        return b""

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        return len(data)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def _enabled_rule(**overrides: object) -> ReminderRule:
    values: dict[str, object] = {
        "id": 1,
        "offset_minutes": 30,
        "message_template": "Warm Up {name}",
        "led_enabled": True,
        "led_red": 255,
        "led_green": 200,
        "led_blue": 0,
        "led_flash_interval_ms": 500,
        "led_flash_duration_seconds": 3,
        "led_chase_duration_seconds": 2,
        "matrix_effect": "solid",
    }
    values.update(overrides)
    return ReminderRule(**values)  # type: ignore[arg-type]


def test_build_matrix_commands() -> None:
    assert build_bright_command(64) == "BRIGHT 64\n"
    assert (
        build_scroll_command(
            red=255,
            green=0,
            blue=0,
            duration_ms=5000,
            message="Warm Up Ada",
        )
        == "SCROLL 255 0 0 5000 0 Warm Up Ada\n"
    )
    assert (
        build_scroll_command(
            red=0,
            green=255,
            blue=0,
            duration_ms=3000,
            message="HELLO",
            effect="rainbow",
        )
        == "SCROLL 0 255 0 3000 1 HELLO\n"
    )
    assert (
        build_scroll_command(
            red=255,
            green=255,
            blue=255,
            duration_ms=2000,
            message="PULSE",
            effect="pulse",
        )
        == "SCROLL 255 255 255 2000 2 PULSE\n"
    )


def test_sanitize_matrix_message() -> None:
    assert sanitize_matrix_message("Warm Up Ada") == "Warm Up Ada"
    assert sanitize_matrix_message("  Hello!!! 😀  ") == "Hello!!!"
    assert sanitize_matrix_message("") == "PAB"
    assert len(sanitize_matrix_message("A" * 120)) == 36


def test_build_scroll_once_and_rainbow_commands() -> None:
    from raspberry_pab.matrix_controller import (
        build_rainbow_command,
        build_scroll_once_command,
    )

    assert (
        build_scroll_once_command(
            red=255,
            green=255,
            blue=255,
            message="MUSIC BREAK",
            effect="rainbow",
        )
        == "SCROLLONCE 255 255 255 1 MUSIC BREAK\n"
    )
    assert build_rainbow_command(duration_ms=3000) == "RAINBOW 3000\n"
    rule = _enabled_rule(
        led_flash_duration_seconds=10,
        led_chase_duration_seconds=5,
    )
    assert matrix_display_duration_ms(rule) == 15000


def test_show_skips_when_globally_disabled() -> None:
    async def run() -> None:
        serial = MockSerial()

        def factory(_settings: Settings, _port: str) -> MockSerial:
            return serial

        controller = MatrixController(
            Settings(matrix_enabled=False, buzzer_port="/dev/ttyUSB0"),
            serial_factory=factory,
        )
        await controller.show(_enabled_rule(), "Warm Up Ada")
        await controller.shutdown()
        assert serial.writes == []

    asyncio.run(run())


def test_show_sends_bright_and_scroll() -> None:
    async def run() -> None:
        serial = MockSerial()

        def factory(_settings: Settings, _port: str) -> MockSerial:
            return serial

        controller = MatrixController(
            Settings(
                matrix_enabled=True,
                buzzer_port="/dev/ttyUSB0",
                matrix_brightness=64,
            ),
            serial_factory=factory,
        )
        await controller.show_test(
            message="Go to Start Line",
            led_red=255,
            led_green=0,
            led_blue=0,
            led_flash_duration_seconds=3,
            led_chase_duration_seconds=2,
            matrix_effect="rainbow",
        )
        await controller.shutdown()
        assert serial.writes[0] == b"PING\n"
        assert serial.writes[1] == b"BRIGHT 64\n"
        assert serial.writes[2] == b"SCROLL 255 0 0 5000 1 Go to Start Line\n"
        assert serial.writes[-1] == b"CLEAR\n"
        assert serial.closed is True

    asyncio.run(run())
