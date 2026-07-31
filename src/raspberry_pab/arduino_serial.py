"""Shared USB-serial helpers for Arduino Nano hardware."""

from __future__ import annotations

import asyncio
from typing import Protocol

from raspberry_pab.config import Settings

HARDWARE_SERIAL_LOCK = asyncio.Lock()


class SerialPort(Protocol):
    def readline(self) -> bytes: ...

    def write(self, data: bytes) -> int: ...

    def flush(self) -> None: ...

    def close(self) -> None: ...


def effective_matrix_port(settings: Settings) -> str:
    if settings.matrix_port:
        return settings.matrix_port
    return settings.buzzer_port


def open_serial_port(settings: Settings, *, port: str) -> SerialPort:
    import serial  # type: ignore[import-untyped]

    return serial.Serial(
        port=port,
        baudrate=settings.matrix_baud,
        timeout=1.0,
        write_timeout=0.5,
        dsrdtr=False,
        rtscts=False,
    )


def _is_ready_line(line: str) -> bool:
    """Accept bare READY or extended banners like 'READY PIXELS 512 FREE 184'."""
    return line == "READY" or line.startswith("READY ")


def wait_for_boot(port: SerialPort, *, timeout: float = 4.0) -> list[str]:
    import time

    boot_lines: list[str] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = port.readline().decode("ascii", errors="replace").strip()
        if not line or not line.isprintable():
            continue
        boot_lines.append(line)
        if _is_ready_line(line):
            return boot_lines
    return boot_lines


def transact_line(
    port: SerialPort,
    command: str,
    expected: set[str],
    *,
    attempts: int,
    response_timeout: float = 1.0,
) -> str:
    import time

    payload = f"{command}\n" if not command.endswith("\n") else command
    for _ in range(attempts):
        port.write(payload.encode("ascii"))
        port.flush()
        deadline = time.monotonic() + response_timeout
        while time.monotonic() < deadline:
            line = port.readline().decode("ascii", errors="replace").strip()
            if not line or not line.isprintable():
                continue
            if line in expected:
                return line
    return ""


def wait_for_ok(port: SerialPort, *, timeout: float) -> bool:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = port.readline().decode("ascii", errors="replace").strip()
        if not line or not line.isprintable():
            continue
        if line == "OK":
            return True
        if line.startswith("ERR"):
            return False
    return False


def handshake(port: SerialPort) -> None:
    boot_lines = wait_for_boot(port)
    if not any(_is_ready_line(line) for line in boot_lines):
        # Board may already be up (no USB reset) — try PING anyway.
        pong = transact_line(port, "PING", {"PONG"}, attempts=3)
        if pong == "PONG":
            return
        raise RuntimeError(f"Arduino did not send READY (got {boot_lines!r})")

    pong = transact_line(port, "PING", {"PONG"}, attempts=5)
    if pong != "PONG":
        raise RuntimeError(f"Arduino did not respond to PING (got {pong!r})")
