"""Background watcher that auto-launches the PAB Roku channel when no HDMI."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.hdmi import hdmi_connected
from raspberry_pab.models import RokuDevice
from raspberry_pab.network_info import preferred_lan_base_url
from raspberry_pab.roku_discovery import discover_devices
from raspberry_pab.roku_ecp import launch_channel

logger = logging.getLogger(__name__)

AUTOCAST_SETTING_KEY = "roku_autocast_enabled"
AUTOCAST_MODE_SETTING_KEY = "roku_autocast_mode"


class RokuAutocastWatcher:
    """Periodically scan for Rokus and launch the sideloaded channel."""

    def __init__(self, settings: Settings, store: ScheduleStore) -> None:
        self._settings = settings
        self._store = store
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self.last_error: str | None = None
        self._last_devices: list[RokuDevice] = []

    @property
    def last_devices(self) -> list[RokuDevice]:
        return list(self._last_devices)

    def effective_mode(self) -> str:
        override = self._store.get_setting(AUTOCAST_MODE_SETTING_KEY)
        if override in {"on", "off", "hdmi-fallback"}:
            return override
        return self._settings.roku_autocast

    def runtime_enabled_override(self) -> bool | None:
        raw = self._store.get_setting(AUTOCAST_SETTING_KEY)
        if raw is None:
            return None
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def set_mode(self, mode: str) -> None:
        if mode not in {"on", "off", "hdmi-fallback"}:
            raise ValueError(f"Invalid autocast mode: {mode}")
        self._store.set_setting(AUTOCAST_MODE_SETTING_KEY, mode)

    def set_enabled(self, enabled: bool) -> None:
        self._store.set_setting(
            AUTOCAST_SETTING_KEY,
            "true" if enabled else "false",
        )

    def should_autocast(self, *, hdmi_is_connected: bool | None = None) -> bool:
        if not self._settings.roku_enabled:
            return False
        override = self.runtime_enabled_override()
        if override is False:
            return False
        mode = self.effective_mode()
        if mode == "off":
            return False
        if mode == "on":
            return True
        # hdmi-fallback
        connected = (
            hdmi_is_connected
            if hdmi_is_connected is not None
            else hdmi_connected()
        )
        return not connected

    def start(self) -> None:
        if not self._settings.roku_enabled:
            logger.info("Roku support disabled (PAB_ROKU_ENABLED)")
            return
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="roku-autocast")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def scan_once(self) -> list[RokuDevice]:
        devices = await discover_devices(
            channel_id=self._settings.roku_channel_id,
        )
        self._last_devices = devices
        return devices

    async def launch_ready_devices(self) -> int:
        """Launch the PAB channel on devices that have it and are not already on it."""
        base_url = preferred_lan_base_url(self._settings.port)
        if not base_url:
            self.last_error = "No LAN address available for Roku deep link"
            logger.warning(self.last_error)
            return 0

        devices = await self.scan_once()
        launched = 0
        for device in devices:
            if not device.has_pab_channel:
                continue
            if device.active_app_id == self._settings.roku_channel_id:
                continue
            try:
                await launch_channel(
                    device.ip,
                    channel_id=self._settings.roku_channel_id,
                    content_id=base_url,
                )
                launched += 1
                self.last_error = None
            except Exception as exc:
                self.last_error = f"{device.ip}: {exc}"
                logger.exception("Failed to launch Roku channel on %s", device.ip)
        return launched

    async def _run(self) -> None:
        interval = max(5.0, self._settings.roku_scan_interval_seconds)
        # Short delay so networking and HDMI DRM settle after boot.
        await asyncio.sleep(5.0)
        while not self._stop.is_set():
            try:
                if self.should_autocast():
                    await self.launch_ready_devices()
            except Exception:
                logger.exception("Roku autocast tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except TimeoutError:
                continue
