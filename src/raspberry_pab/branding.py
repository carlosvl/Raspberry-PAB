"""Branding helpers for kiosk title and logo."""

from __future__ import annotations

from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import BrandingResponse

DISPLAY_TITLE_KEY = "display_title"
LOGO_UPDATED_AT_KEY = "logo_updated_at"
BOARD_FONT_SCALE_KEY = "board_font_scale"
DEFAULT_BOARD_FONT_SCALE = 100
MIN_BOARD_FONT_SCALE = 70
MAX_BOARD_FONT_SCALE = 140
MAX_LOGO_BYTES = 512 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def effective_display_title(settings: Settings, store: ScheduleStore) -> str:
    override = store.get_setting(DISPLAY_TITLE_KEY)
    if override is not None and override.strip():
        return override.strip()
    return settings.display_title


def effective_board_font_scale(store: ScheduleStore) -> int:
    raw = store.get_setting(BOARD_FONT_SCALE_KEY)
    if raw is None or not str(raw).strip():
        return DEFAULT_BOARD_FONT_SCALE
    try:
        value = int(str(raw).strip())
    except ValueError:
        return DEFAULT_BOARD_FONT_SCALE
    return max(MIN_BOARD_FONT_SCALE, min(MAX_BOARD_FONT_SCALE, value))


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


def branding_response(settings: Settings, store: ScheduleStore) -> BrandingResponse:
    return BrandingResponse(
        display_title=effective_display_title(settings, store),
        board_font_scale=effective_board_font_scale(store),
        has_logo=has_logo(settings),
        logo_url=logo_url(settings, store),
    )
