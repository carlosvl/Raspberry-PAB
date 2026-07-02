"""Tests for Arduino buzzer controller behavior."""

from __future__ import annotations

import asyncio

from raspberry_pab.buzzer_controller import BuzzerController, build_beep_command
from raspberry_pab.config import Settings
from raspberry_pab.models import ReminderRule


class MockSerial:
    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.closed = False
        self._reads = [b"READY\n", b"PONG\n", b"OK\n"]

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
        "buzzer_enabled": True,
        "buzzer_pitch_hz": 2500,
        "buzzer_volume": 80,
        "buzzer_count": 3,
        "buzzer_beep_ms": 200,
        "buzzer_gap_ms": 150,
    }
    values.update(overrides)
    return ReminderRule(**values)  # type: ignore[arg-type]


def test_build_beep_command() -> None:
    assert build_beep_command(
        pitch_hz=2500,
        volume=80,
        count=3,
        beep_ms=200,
        gap_ms=150,
    ) == "BEEP 2500 80 3 200 150\n"


def test_beep_skips_when_globally_disabled() -> None:
    async def run() -> None:
        serial = MockSerial()

        def factory(_settings: Settings) -> MockSerial:
            return serial

        controller = BuzzerController(
            Settings(buzzer_enabled=False, buzzer_port="/dev/ttyUSB0"),
            serial_factory=factory,
        )
        await controller.beep(_enabled_rule())
        await controller.shutdown()
        assert serial.writes == []

    asyncio.run(run())


def test_beep_sends_mode_and_pattern() -> None:
    async def run() -> None:
        serial = MockSerial()

        def factory(_settings: Settings) -> MockSerial:
            return serial

        controller = BuzzerController(
            Settings(
                buzzer_enabled=True,
                buzzer_port="/dev/ttyUSB0",
                buzzer_mode="active",
            ),
            serial_factory=factory,
        )
        await controller.beep_test(
            buzzer_pitch_hz=2500,
            buzzer_volume=80,
            buzzer_count=3,
            buzzer_beep_ms=200,
            buzzer_gap_ms=150,
        )
        await controller.shutdown()
        assert serial.writes[0] == b"PING\n"
        assert serial.writes[1] == b"BEEP 2500 80 3 200 150\n"
        assert serial.writes[-1] == b"STOP\n"
        assert serial.closed is True

    asyncio.run(run())
