"""Tests for schedule CSV import parsing."""

from __future__ import annotations

from datetime import date, time

import pytest

from raspberry_pab.csv_import import parse_schedule_csv


def test_parse_csv_with_headers() -> None:
    csv_text = """name,race,call_up,start_time
Carlos,Pro Men,10:45,11:00
Ana,Pro Women,,11:15
"""
    schedule = parse_schedule_csv(csv_text, event_date=date(2026, 6, 21))
    assert schedule.event_date == date(2026, 6, 21)
    assert len(schedule.participants) == 2
    assert schedule.participants[0].name == "Carlos"
    assert schedule.participants[0].race == "Pro Men"
    assert schedule.participants[0].call_up == "10:45"
    assert schedule.participants[0].start_time == time(11, 0)
    assert schedule.participants[1].call_up is None
    assert schedule.participants[1].race == "Pro Women"


def test_parse_legacy_name_start_only() -> None:
    csv_text = "Carlos,11:00\nAna,11:15\n"
    schedule = parse_schedule_csv(csv_text, event_date=date(2026, 6, 21))
    assert [p.name for p in schedule.participants] == ["Carlos", "Ana"]
    assert schedule.participants[0].start_time == time(11, 0)
    assert schedule.participants[0].race == ""


def test_parse_csv_event_date_column() -> None:
    csv_text = """name,start_time,event_date
Carlos,11:00,2026-07-04
"""
    schedule = parse_schedule_csv(csv_text)
    assert schedule.event_date == date(2026, 7, 4)


def test_parse_csv_requires_event_date() -> None:
    with pytest.raises(ValueError, match="event_date"):
        parse_schedule_csv("name,start_time\nCarlos,11:00\n")
