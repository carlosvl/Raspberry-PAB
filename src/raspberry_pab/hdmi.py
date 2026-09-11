"""Detect whether an HDMI display is connected (Linux DRM sysfs)."""

from __future__ import annotations

from pathlib import Path

DRM_CLASS = Path("/sys/class/drm")


def hdmi_connected(drm_root: Path | None = None) -> bool:
    """Return True if any HDMI connector reports status=connected.

    On non-Pi hosts (or when sysfs is missing) returns False so auto-cast
    can treat the machine as "no HDMI" in tests / Mac development.
    """
    root = drm_root if drm_root is not None else DRM_CLASS
    if not root.is_dir():
        return False
    for status_path in root.glob("card*-HDMI-A-*/status"):
        try:
            value = status_path.read_text(encoding="utf-8").strip().lower()
        except OSError:
            continue
        if value == "connected":
            return True
    return False
