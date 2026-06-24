#!/usr/bin/env python3
"""Verify lotus-lamp + bleak install and optional BLE connection test."""

from __future__ import annotations

import asyncio
import os
import sys
from importlib.metadata import PackageNotFoundError, version


def _pkg_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def main() -> int:
    try:
        import bleak  # noqa: F401
        import lotus_lamp  # noqa: F401
    except ImportError as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        print("Install into the project venv:", file=sys.stderr)
        print("  .venv/bin/pip install lotus-lamp bleak", file=sys.stderr)
        return 1

    print(f"Packages OK (bleak {_pkg_version('bleak')}, lotus-lamp {_pkg_version('lotus-lamp')})")

    address = os.environ.get("PAB_LED_ADDRESS", "").strip()
    name = os.environ.get("PAB_LED_NAME", "MELKL-OT21 CB").strip()
    if not address:
        print("Set PAB_LED_ADDRESS to run a live BLE test.")
        return 0

    async def ble_test() -> None:
        from lotus_lamp import DeviceConfig, LotusLamp

        lamp = LotusLamp(device_config=DeviceConfig(name=name, address=address))
        await lamp.connect()
        await lamp.power_on()
        await lamp.set_rgb(255, 200, 0)
        await asyncio.sleep(2)
        await lamp.power_off()
        await lamp.disconnect()
        print("BLE test OK: on -> color -> off")

    try:
        asyncio.run(ble_test())
    except Exception as exc:
        print(f"BLE test failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
