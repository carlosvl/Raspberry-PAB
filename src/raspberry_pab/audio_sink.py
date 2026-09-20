"""Prefer Bluetooth A2DP sinks, then HDMI, for alert/music playback."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from raspberry_pab.config import Settings

logger = logging.getLogger(__name__)

BT_SPEAKER_MAC_KEY = "bt_speaker_mac"
BT_SPEAKER_NAME_KEY = "bt_speaker_name"

_MAC_COMPACT = re.compile(r"[^0-9a-fA-F]")


def _runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    if "XDG_RUNTIME_DIR" not in env:
        runtime = Path(f"/run/user/{os.getuid()}")
        if runtime.is_dir():
            env["XDG_RUNTIME_DIR"] = str(runtime)
    return env


def list_sink_names() -> list[str]:
    """Return PipeWire/Pulse sink names via pactl."""
    if not shutil.which("pactl"):
        return []
    try:
        result = subprocess.run(
            ["pactl", "list", "short", "sinks"],
            check=False,
            capture_output=True,
            text=True,
            env=_runtime_env(),
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    names: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            names.append(parts[1])
    return names


def mac_compact(mac: str) -> str:
    return _MAC_COMPACT.sub("", mac).lower()


def find_bluez_sink(mac: str | None = None) -> str | None:
    """Return a bluez_output sink, optionally matching a device MAC."""
    sinks = list_sink_names()
    compact = mac_compact(mac) if mac else ""
    bluez = [name for name in sinks if "bluez_output" in name.lower()]
    if not bluez:
        return None
    if compact:
        for name in bluez:
            if compact in name.lower().replace(":", "").replace("_", ""):
                return name
            if compact in re.sub(r"[^0-9a-f]", "", name.lower()):
                return name
    return bluez[0]


def find_hdmi_sink() -> str | None:
    for name in list_sink_names():
        if "hdmi" in name.lower():
            return name
    return "alsa_output.platform-fef00700.hdmi.hdmi-stereo"


def resolve_playback_sink(
    settings: Settings,
    *,
    preferred_mac: str | None = None,
) -> tuple[str | None, str]:
    """Pick sink: env override → Bluetooth → HDMI.

    Returns (sink_name, source) where source is override|bluetooth|hdmi|none.
    """
    override = settings.sound_sink.strip()
    if override:
        return override, "override"

    bluez = find_bluez_sink(preferred_mac)
    if bluez:
        return bluez, "bluetooth"

    hdmi = find_hdmi_sink()
    if hdmi:
        return hdmi, "hdmi"
    return None, "none"
