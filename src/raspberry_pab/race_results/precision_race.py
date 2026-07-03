"""Parse the Precision Race MCA index page."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

_RACE_HEADING = re.compile(
    r"^Race\s*#?\s*(\d+[A-Za-z]?)\s*\|\s*(.+?):\s*(.+)$",
    re.IGNORECASE,
)
_DATE_RANGE = re.compile(
    r"^(?P<mon>[A-Za-z.]+)\s*(?P<day1>\d{1,2})/(?P<day2>\d{1,2})$",
    re.IGNORECASE,
)
_MONTHS = {
    "jan": 1,
    "jan.": 1,
    "feb": 2,
    "feb.": 2,
    "mar": 3,
    "mar.": 3,
    "apr": 4,
    "apr.": 4,
    "may": 5,
    "may.": 5,
    "jun": 6,
    "jun.": 6,
    "june": 6,
    "jul": 7,
    "jul.": 7,
    "july": 7,
    "aug": 8,
    "aug.": 8,
    "sep": 9,
    "sept": 9,
    "sept.": 9,
    "oct": 10,
    "oct.": 10,
    "nov": 11,
    "nov.": 11,
    "dec": 12,
    "dec.": 12,
}


@dataclass(frozen=True)
class ParsedRaceEvent:
    season_year: int
    race_number: str
    venue_label: str
    date_saturday: date
    date_sunday: date
    iyr_series_id: str
    iyr_base_url: str
    source_url: str


def _parse_month_day(year: int, month_token: str, day: int) -> date:
    month_key = month_token.strip().lower()
    month = _MONTHS.get(month_key)
    if month is None:
        month_key = month_key.rstrip(".")
        month = _MONTHS.get(month_key)
    if month is None:
        raise ValueError(f"Unknown month token: {month_token!r}")
    return date(year, month, day)


def parse_weekend_dates(year: int, date_text: str) -> tuple[date, date]:
    match = _DATE_RANGE.match(date_text.strip())
    if match is None:
        raise ValueError(f"Could not parse MCA weekend dates from {date_text!r}")
    saturday = _parse_month_day(year, match.group("mon"), int(match.group("day1")))
    sunday = _parse_month_day(year, match.group("mon"), int(match.group("day2")))
    return saturday, sunday


def extract_iyr_series_id(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    series_id = query.get("id", [None])[0]
    if not series_id:
        raise ValueError(f"No IYR series id in URL: {url}")
    return str(series_id)


def build_iyr_base_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def parse_race_heading_text(
    heading_text: str,
    *,
    season_year: int,
    source_url: str,
    iyr_url: str | None,
) -> ParsedRaceEvent | None:
    match = _RACE_HEADING.match(heading_text.strip())
    if match is None or not iyr_url:
        return None
    race_number, date_text, venue_label = match.groups()
    saturday, sunday = parse_weekend_dates(season_year, date_text)
    return ParsedRaceEvent(
        season_year=season_year,
        race_number=race_number.upper(),
        venue_label=venue_label.strip(),
        date_saturday=saturday,
        date_sunday=sunday,
        iyr_series_id=extract_iyr_series_id(iyr_url),
        iyr_base_url=build_iyr_base_url(iyr_url),
        source_url=source_url,
    )


def parse_precision_race_mca_html(html: str, *, source_url: str) -> list[ParsedRaceEvent]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[ParsedRaceEvent] = []
    season_year: int | None = None
    for element in soup.find_all(["h2", "h3"]):
        if element.name == "h2":
            text = element.get_text(" ", strip=True)
            year_match = re.match(r"^(\d{4})\b", text)
            if year_match and "MN Cycling" in text:
                season_year = int(year_match.group(1))
            continue
        if element.name != "h3" or season_year is None:
            continue
        anchor = element.find("a", href=True)
        heading_text = element.get_text(" ", strip=True)
        iyr_url = anchor["href"] if anchor is not None else None
        parsed = parse_race_heading_text(
            heading_text,
            season_year=season_year,
            source_url=source_url,
            iyr_url=iyr_url,
        )
        if parsed is not None:
            events.append(parsed)
    return events
