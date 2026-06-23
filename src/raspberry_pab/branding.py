"""Branding helpers for kiosk title and logo."""

from __future__ import annotations

from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore

DISPLAY_TITLE_KEY = "display_title"
LOGO_UPDATED_AT_KEY = "logo_updated_at"
MAX_LOGO_BYTES = 512 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def effective_display_title(settings: Settings, store: ScheduleStore) -> str:
    override = store.get_setting(DISPLAY_TITLE_KEY)
    if override is not None and override.strip():
        return override.strip()
    return settings.display_title


def logo_updated_at(store: ScheduleStore) -> str | None:
    value = store.get_setting(LOGO_UPDATED_AT_KEY)
    return value if value else None


def has_logo(settings: Settings) -> bool:
    return settings.logo_path.is_file()


def logo_url(settings: Settings, store: ScheduleStore) -> str | None:
    if not has_logo(settings):
        return None
    version = logo_updated_at(store) or str(int(settings.logo_path.stat().st_mtime))
    return f"/api/branding/logo?v={version}"


def branding_response(settings: Settings, store: ScheduleStore) -> dict[str, str | bool | None]:
    return {
        "display_title": effective_display_title(settings, store),
        "has_logo": has_logo(settings),
        "logo_url": logo_url(settings, store),
    }
