"""Interval music-break playlist config and slot math."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import MusicBreakConfig

MUSIC_BREAK_CONFIG_KEY = "music_break_config"
MUSIC_BREAK_FIRED_KEY = "music_break_fired"
DEFAULT_INTERVAL_MINUTES = 15
DEFAULT_START_TIME = "09:00"
DEFAULT_VOLUME = 80
DEFAULT_PULSE_MS = 500


@dataclass(frozen=True)
class MusicBreakSlot:
    """A due playlist slot. slot_index is 1-based (first play at start+interval)."""

    slot_index: int
    fire_at: datetime
    sound_id: int


def parse_start_time(value: str) -> time:
    cleaned = value.strip()
    try:
        hour_s, minute_s = cleaned.split(":", 1)
        hour = int(hour_s)
        minute = int(minute_s)
    except ValueError as exc:
        raise ValueError(f"Invalid start_time {value!r}") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid start_time {value!r}")
    return time(hour, minute)


def default_config() -> MusicBreakConfig:
    return MusicBreakConfig()


def load_config(store: ScheduleStore) -> MusicBreakConfig:
    raw = store.get_setting(MUSIC_BREAK_CONFIG_KEY)
    if not raw:
        return default_config()
    try:
        data = json.loads(raw)
        return MusicBreakConfig.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return default_config()


def save_config(store: ScheduleStore, config: MusicBreakConfig) -> None:
    store.set_setting(
        MUSIC_BREAK_CONFIG_KEY,
        json.dumps(config.model_dump(mode="json")),
    )


def playlist_start_at(day: date, start_time_text: str) -> datetime:
    return datetime.combine(day, parse_start_time(start_time_text))


def slot_for_index(
    *,
    day: date,
    config: MusicBreakConfig,
    slot_index: int,
) -> MusicBreakSlot | None:
    if slot_index < 1 or not config.sound_ids:
        return None
    start = playlist_start_at(day, config.start_time)
    fire_at = start + timedelta(minutes=config.interval_minutes * slot_index)
    sound_id = config.sound_ids[(slot_index - 1) % len(config.sound_ids)]
    return MusicBreakSlot(slot_index=slot_index, fire_at=fire_at, sound_id=sound_id)


def current_slot_index(now: datetime, config: MusicBreakConfig) -> int | None:
    """Return 1-based slot index if now is at/after the first interval, else None."""
    if not config.enabled or not config.sound_ids or config.interval_minutes < 1:
        return None
    start = playlist_start_at(now.date(), config.start_time)
    if now < start + timedelta(minutes=config.interval_minutes):
        return None
    elapsed = now - start
    slot = int(elapsed.total_seconds() // (config.interval_minutes * 60))
    return slot if slot >= 1 else None


def due_slot(now: datetime, config: MusicBreakConfig) -> MusicBreakSlot | None:
    index = current_slot_index(now, config)
    if index is None:
        return None
    return slot_for_index(day=now.date(), config=config, slot_index=index)


def next_slot_after(now: datetime, config: MusicBreakConfig) -> MusicBreakSlot | None:
    if not config.enabled or not config.sound_ids or config.interval_minutes < 1:
        return None
    start = playlist_start_at(now.date(), config.start_time)
    first = start + timedelta(minutes=config.interval_minutes)
    if now < first:
        return slot_for_index(day=now.date(), config=config, slot_index=1)
    current = current_slot_index(now, config)
    if current is None:
        return slot_for_index(day=now.date(), config=config, slot_index=1)
    return slot_for_index(day=now.date(), config=config, slot_index=current + 1)


def load_fired_slots(store: ScheduleStore) -> dict[str, list[int]]:
    raw = store.get_setting(MUSIC_BREAK_FIRED_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        result: dict[str, list[int]] = {}
        for key, value in data.items():
            if isinstance(value, list):
                result[str(key)] = [int(item) for item in value]
        return result
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def save_fired_slots(store: ScheduleStore, fired: dict[str, list[int]]) -> None:
    store.set_setting(MUSIC_BREAK_FIRED_KEY, json.dumps(fired))


def mark_slot_fired(store: ScheduleStore, day: date, slot_index: int) -> None:
    fired = load_fired_slots(store)
    key = day.isoformat()
    slots = set(fired.get(key, []))
    slots.add(slot_index)
    # Keep only today to avoid unbounded growth.
    fired = {key: sorted(slots)}
    save_fired_slots(store, fired)


def was_slot_fired(store: ScheduleStore, day: date, slot_index: int) -> bool:
    fired = load_fired_slots(store)
    return slot_index in fired.get(day.isoformat(), [])


def hsv_to_rgb(hue: float, saturation: float = 1.0, value: float = 1.0) -> tuple[int, int, int]:
    """Convert HSV (hue 0-360) to 8-bit RGB."""
    hue = hue % 360.0
    chroma = value * saturation
    x = chroma * (1 - abs((hue / 60.0) % 2 - 1))
    m = value - chroma
    if hue < 60:
        r, g, b = chroma, x, 0.0
    elif hue < 120:
        r, g, b = x, chroma, 0.0
    elif hue < 180:
        r, g, b = 0.0, chroma, x
    elif hue < 240:
        r, g, b = 0.0, x, chroma
    elif hue < 300:
        r, g, b = x, 0.0, chroma
    else:
        r, g, b = chroma, 0.0, x
    return (
        int(round((r + m) * 255)),
        int(round((g + m) * 255)),
        int(round((b + m) * 255)),
    )
