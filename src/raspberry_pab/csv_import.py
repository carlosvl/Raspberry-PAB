"""Parse comma-separated schedule CSV into ScheduleImport."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, time

from raspberry_pab.models import ScheduleImport, ScheduleParticipantImport

_HEADER_ALIASES: dict[str, str] = {
    "name": "name",
    "rider": "name",
    "participant": "name",
    "athlete": "name",
    "race": "race",
    "category": "race",
    "call_up": "call_up",
    "callup": "call_up",
    "call-up": "call_up",
    "call up": "call_up",
    "start_time": "start_time",
    "start": "start_time",
    "start time": "start_time",
    "event_date": "event_date",
    "date": "event_date",
    "event date": "event_date",
}


def _normalize_header(raw: str) -> str | None:
    key = raw.strip().lower().replace("_", " ").replace("-", " ")
    key = " ".join(key.split())
    compact = key.replace(" ", "_")
    if compact in _HEADER_ALIASES:
        return _HEADER_ALIASES[compact]
    if key in _HEADER_ALIASES:
        return _HEADER_ALIASES[key]
    return _HEADER_ALIASES.get(raw.strip().lower())


def _parse_time(value: str) -> time:
    text = value.strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(text, fmt).time().replace(second=0, microsecond=0)
        except ValueError:
            continue
    raise ValueError(f"Invalid time: {value!r}")


def _parse_date(value: str) -> date:
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value!r}")


def parse_schedule_csv(
    content: str,
    *,
    event_date: date | None = None,
) -> ScheduleImport:
    """Parse CSV text into a schedule import.

    Accepts a header row. Required columns: ``name``, ``start_time``.
    Optional: ``race``, ``call_up``, ``event_date``.
    Legacy two-column ``name,start_time`` works with or without a header when
    the first row looks like data (no recognized headers).
    """
    text = content.strip()
    if not text:
        raise ValueError("CSV is empty")

    # Strip UTF-8 BOM if present
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")

    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError("CSV is empty")

    first = [cell.strip() for cell in rows[0]]
    mapped = [_normalize_header(cell) for cell in first]
    has_header = any(item is not None for item in mapped)

    if has_header:
        field_index: dict[str, int] = {}
        for index, field in enumerate(mapped):
            if field and field not in field_index:
                field_index[field] = index
        data_rows = rows[1:]
        columns = sorted(field_index)
    else:
        # Legacy: name,start_time[,race][,call_up]
        if len(first) < 2:
            raise ValueError("CSV needs at least name and start_time columns")
        field_index = {"name": 0, "start_time": 1}
        if len(first) >= 3:
            field_index["race"] = 2
        if len(first) >= 4:
            field_index["call_up"] = 3
        data_rows = rows
        columns = sorted(field_index)

    if "name" not in field_index or "start_time" not in field_index:
        raise ValueError("CSV must include name and start_time columns")

    participants: list[ScheduleParticipantImport] = []
    row_event_date: date | None = None

    for row_number, row in enumerate(data_rows, start=2 if has_header else 1):
        if not any(cell.strip() for cell in row):
            continue

        def cell(field: str) -> str:
            index = field_index.get(field)
            if index is None or index >= len(row):
                return ""
            return row[index].strip()

        name = cell("name")
        start_raw = cell("start_time")
        if not name or not start_raw:
            raise ValueError(f"Row {row_number}: name and start_time are required")

        race = cell("race")
        call_up_raw = cell("call_up")
        call_up = _parse_time(call_up_raw) if call_up_raw else None
        date_raw = cell("event_date")
        if date_raw:
            parsed_date = _parse_date(date_raw)
            if row_event_date is None:
                row_event_date = parsed_date
            elif parsed_date != row_event_date:
                raise ValueError("CSV contains multiple event_date values")

        participants.append(
            ScheduleParticipantImport(
                name=name,
                start_time=_parse_time(start_raw),
                race=race,
                call_up=call_up,
            )
        )

    resolved_date = event_date or row_event_date
    if resolved_date is None:
        raise ValueError("event_date is required (form field or CSV column)")

    return ScheduleImport(
        event_date=resolved_date,
        participants=participants,
        reminder_rules=[],
    )
