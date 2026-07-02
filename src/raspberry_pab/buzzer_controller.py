"""Serial buzzer control for reminder alerts via Arduino Nano."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from typing import Protocol

from raspberry_pab.config import Settings
from raspberry_pab.models import ReminderRule

logger = logging.getLogger(__name__)

SerialFactory = Callable[[Settings], object]


class _SerialPort(Protocol):
    def readline(self) -> bytes: ...

    def write(self, data: bytes) -> int: ...

    def flush(self) -> None: ...

    def close(self) -> None: ...


def _default_serial_factory(settings: Settings) -> _SerialPort:
    import serial  # type: ignore[import-untyped]

    return serial.Serial(
        port=settings.buzzer_port,
        baudrate=settings.buzzer_baud,
        timeout=1.0,
        write_timeout=0.5,
        dsrdtr=False,
        rtscts=False,
    )


def build_mode_command(mode: str) -> str:
    return f"MODE {mode}\n"


def build_beep_command(
    *,
    pitch_hz: int,
    volume: int,
    count: int,
    beep_ms: int,
    gap_ms: int,
) -> str:
    return f"BEEP {pitch_hz} {volume} {count} {beep_ms} {gap_ms}\n"


def build_stop_command() -> str:
    return "STOP\n"


def estimate_beep_seconds(*, count: int, beep_ms: int, gap_ms: int) -> float:
    return (count * beep_ms + max(0, count - 1) * gap_ms) / 1000.0 + 0.75


class BuzzerController:
    """Sends beep patterns to an Arduino over USB serial."""

    def __init__(
        self,
        settings: Settings,
        *,
        serial_factory: SerialFactory | None = None,
    ) -> None:
        self._settings = settings
        self._serial_factory = serial_factory or _default_serial_factory
        self._lock = asyncio.Lock()
        self._beep_task: asyncio.Task[None] | None = None

    async def beep(self, rule: ReminderRule) -> None:
        if not self._should_beep(rule):
            return
        await self._start_beep(
            pitch_hz=rule.buzzer_pitch_hz,
            volume=rule.buzzer_volume,
            count=rule.buzzer_count,
            beep_ms=rule.buzzer_beep_ms,
            gap_ms=rule.buzzer_gap_ms,
        )

    async def beep_test(
        self,
        *,
        buzzer_pitch_hz: int,
        buzzer_volume: int,
        buzzer_count: int,
        buzzer_beep_ms: int,
        buzzer_gap_ms: int,
    ) -> None:
        if not self._settings.buzzer_enabled or not self._settings.buzzer_port:
            return
        await self._start_beep(
            pitch_hz=buzzer_pitch_hz,
            volume=buzzer_volume,
            count=buzzer_count,
            beep_ms=buzzer_beep_ms,
            gap_ms=buzzer_gap_ms,
            wait=True,
        )

    async def shutdown(self) -> None:
        if self._beep_task and not self._beep_task.done():
            self._beep_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._beep_task
        self._beep_task = None

    async def _start_beep(
        self,
        *,
        pitch_hz: int,
        volume: int,
        count: int,
        beep_ms: int,
        gap_ms: int,
        wait: bool = False,
    ) -> None:
        if self._beep_task and not self._beep_task.done():
            self._beep_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._beep_task
        self._beep_task = asyncio.create_task(
            self._run_beep(
                pitch_hz=pitch_hz,
                volume=volume,
                count=count,
                beep_ms=beep_ms,
                gap_ms=gap_ms,
            ),
            name="buzzer-beep",
        )
        if wait:
            await self._beep_task

    def _should_beep(self, rule: ReminderRule) -> bool:
        return (
            self._settings.buzzer_enabled
            and bool(self._settings.buzzer_port)
            and rule.buzzer_enabled
        )

    async def _run_beep(
        self,
        *,
        pitch_hz: int,
        volume: int,
        count: int,
        beep_ms: int,
        gap_ms: int,
    ) -> None:
        async with self._lock:
            try:
                await asyncio.to_thread(
                    self._execute_beep_sequence,
                    pitch_hz=pitch_hz,
                    volume=volume,
                    count=count,
                    beep_ms=beep_ms,
                    gap_ms=gap_ms,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Buzzer beep failed")

    def _transact_line(
        self,
        port: _SerialPort,
        command: str,
        expected: set[str],
        *,
        attempts: int,
    ) -> str:
        payload = f"{command}\n" if not command.endswith("\n") else command
        for _ in range(attempts):
            port.write(payload.encode("ascii"))
            port.flush()
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                line = port.readline().decode("ascii", errors="replace").strip()
                if not line or not line.isprintable():
                    continue
                if line in expected:
                    return line
        return ""

    def _wait_for_boot(self, port: _SerialPort, *, timeout: float = 2.5) -> list[str]:
        boot_lines: list[str] = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = port.readline().decode("ascii", errors="replace").strip()
            if not line or not line.isprintable():
                continue
            boot_lines.append(line)
            if line == "READY":
                return boot_lines
        return boot_lines

    def _execute_beep_sequence(
        self,
        *,
        pitch_hz: int,
        volume: int,
        count: int,
        beep_ms: int,
        gap_ms: int,
    ) -> str:
        port = self._serial_factory(self._settings)
        boot_lines: list[str] = []
        response_lines: list[str] = []
        try:
            boot_lines = self._wait_for_boot(port)
            if "READY" not in boot_lines:
                raise RuntimeError(
                    f"Arduino did not send READY (got {boot_lines!r})"
                )

            pong = self._transact_line(port, "PING", {"PONG"}, attempts=5)
            if pong != "PONG":
                raise RuntimeError(f"Arduino did not respond to PING (got {pong!r})")

            beep_cmd = build_beep_command(
                pitch_hz=pitch_hz,
                volume=volume,
                count=count,
                beep_ms=beep_ms,
                gap_ms=gap_ms,
            )
            port.write(beep_cmd.encode("ascii"))
            port.flush()

            ok_deadline = time.monotonic() + estimate_beep_seconds(
                count=count,
                beep_ms=beep_ms,
                gap_ms=gap_ms,
            )
            while time.monotonic() < ok_deadline:
                line = port.readline().decode("ascii", errors="replace").strip()
                if not line or not line.isprintable():
                    continue
                response_lines.append(line)
                if line == "OK":
                    return "OK"
            return response_lines[-1] if response_lines else "timeout"
        finally:
            with contextlib.suppress(Exception):
                port.write(build_stop_command().encode("ascii"))
                port.flush()
            port.close()
