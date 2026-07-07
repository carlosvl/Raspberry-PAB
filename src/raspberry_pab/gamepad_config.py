"""Detect USB gamepad joystick devices on Linux."""

from __future__ import annotations

import os
import re
from pathlib import Path

_INPUT_DEVICES = Path("/proc/bus/input/devices")
_GAMEPAD_NAME_HINTS = ("gamepad", "joystick", "controller", "xbox", "playstation")


def parse_input_devices(text: str) -> list[dict[str, str]]:
    blocks = re.split(r"\n(?=I:)", text.strip())
    devices: list[dict[str, str]] = []
    for block in blocks:
        if not block.strip():
            continue
        entry: dict[str, str] = {}
        for line in block.splitlines():
            if line.startswith("N: Name="):
                entry["name"] = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("H: Handlers="):
                entry["handlers"] = line.split("=", 1)[1].strip()
        if entry:
            devices.append(entry)
    return devices


def js_handler_from_handlers(handlers: str) -> str | None:
    for token in handlers.split():
        if token.startswith("js") and token[2:].isdigit():
            return f"/dev/input/{token}"
    return None


def find_gamepad_js_device(
    *,
    devices_text: str | None = None,
    input_devices_path: Path = _INPUT_DEVICES,
) -> str | None:
    if devices_text is None:
        if not input_devices_path.is_file():
            return None
        devices_text = input_devices_path.read_text(encoding="utf-8")

    for entry in parse_input_devices(devices_text):
        name = entry.get("name", "").lower()
        handlers = entry.get("handlers", "")
        js_path = js_handler_from_handlers(handlers)
        if js_path is None:
            continue
        if any(hint in name for hint in _GAMEPAD_NAME_HINTS):
            return js_path

    for entry in parse_input_devices(devices_text):
        js_path = js_handler_from_handlers(entry.get("handlers", ""))
        if js_path and os.path.exists(js_path):
            return js_path
    return None
