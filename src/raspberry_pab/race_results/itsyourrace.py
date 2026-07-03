"""Parse ITS YOUR RACE results pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

_BIB_RE = re.compile(r"\(#\s*(\d+)\)")
_RACE_DATE = re.compile(
    r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
    re.IGNORECASE,
)
_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}


@dataclass(frozen=True)
class IyrCategoryOption:
    eid: str
    label: str


@dataclass(frozen=True)
class ParsedResultRow:
    place: int
    raw_name: str
    bib: str | None
    team_name: str | None
    laps: int | None
    total_time: str | None
    total_distance: str | None


@dataclass(frozen=True)
class ParsedIyrSession:
    series_id: str
    season_year: int
    eid: str
    category_label: str
    race_date: date
    results_status: str
    results_url: str
    rows: list[ParsedResultRow]
    page_count: int


def parse_race_date(text: str) -> date | None:
    match = _RACE_DATE.search(text)
    if match is None:
        return None
    month = _MONTHS.get(match.group(2).lower())
    if month is None:
        return None
    return date(int(match.group(4)), month, int(match.group(3)))


def parse_category_options(html: str) -> list[IyrCategoryOption]:
    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select", id="ddlRace")
    if select is None:
        return []
    options: list[IyrCategoryOption] = []
    for option in select.find_all("option"):
        value = (option.get("value") or "").strip()
        label = option.get_text(" ", strip=True)
        if value and label and label.lower() != "select race":
            options.append(IyrCategoryOption(eid=value, label=label))
    return options


def build_series_landing_url(*, base_url: str, series_id: str) -> str:
    parsed = urlparse(base_url)
    path = parsed.path or "/Results.aspx"
    if not path.endswith(".aspx"):
        path = "/Results.aspx"
    query = urlencode({"id": series_id})
    return urlunparse((parsed.scheme, parsed.netloc, path, "", query, ""))


def build_results_url(
    *,
    base_url: str,
    series_id: str,
    season_year: int,
    eid: str,
    page: int = 1,
) -> str:
    parsed = urlparse(base_url)
    path = parsed.path or "/Results.aspx"
    if not path.endswith(".aspx"):
        path = "/Results.aspx"
    query = urlencode(
        {
            "id": series_id,
            "y": season_year,
            "eid": eid,
            "g": "A",
            "amin": 0,
            "amax": 199,
            "pg": page,
        }
    )
    return urlunparse((parsed.scheme, parsed.netloc, path, "", query, ""))


def _parse_result_rows(soup: BeautifulSoup) -> list[ParsedResultRow]:
    rows: list[ParsedResultRow] = []
    for row in soup.select("tr"):
        place_cell = row.find("td", class_="placeOverall")
        name_cell = row.find("td", class_="name")
        if place_cell is None or name_cell is None:
            continue
        place_text = place_cell.get_text(" ", strip=True)
        if not place_text.isdigit():
            continue
        name_html = name_cell.get_text(" ", strip=True)
        bib_match = _BIB_RE.search(name_html)
        bib = bib_match.group(1) if bib_match else None
        raw_name = _BIB_RE.sub("", name_html).strip()
        team_cell = row.find("td", id="tdTeamName")
        if team_cell is None:
            team_cells = row.find_all("td", class_="name")
            team_cell = team_cells[1] if len(team_cells) > 1 else None
        laps_cell = row.find("td", class_="lapCount")
        time_cell = row.find("td", class_="lapTotalTime")
        distance_cell = row.find("td", class_="lapTotalDistance")
        rows.append(
            ParsedResultRow(
                place=int(place_text),
                raw_name=raw_name,
                bib=bib,
                team_name=team_cell.get_text(" ", strip=True) if team_cell else None,
                laps=int(laps_cell.get_text(strip=True))
                if laps_cell and laps_cell.get_text(strip=True).isdigit()
                else None,
                total_time=time_cell.get_text(" ", strip=True) if time_cell else None,
                total_distance=distance_cell.get_text(" ", strip=True)
                if distance_cell
                else None,
            )
        )
    return rows


def parse_results_page_html(
    html: str,
    *,
    results_url: str,
    series_id: str,
    season_year: int,
    eid: str,
) -> ParsedIyrSession:
    soup = BeautifulSoup(html, "html.parser")
    header = soup.select_one(".results-header-box h3")
    category_label = header.get_text(" ", strip=True) if header else ""
    race_date = None
    for paragraph in soup.select(".results-header-box p"):
        race_date = parse_race_date(paragraph.get_text(" ", strip=True))
        if race_date is not None:
            break
    if race_date is None:
        raise ValueError(f"Could not parse race date from {results_url}")
    status_el = soup.select_one(".results-unofficial, .results-official")
    results_status = status_el.get_text(" ", strip=True) if status_el else "unknown"
    page_select = soup.find("select", id="ddlPageLaps")
    page_count = len(page_select.find_all("option")) if page_select is not None else 1
    return ParsedIyrSession(
        series_id=series_id,
        season_year=season_year,
        eid=eid,
        category_label=category_label,
        race_date=race_date,
        results_status=results_status,
        results_url=results_url,
        rows=_parse_result_rows(soup),
        page_count=max(page_count, 1),
    )


def merge_result_pages(pages: list[ParsedIyrSession]) -> ParsedIyrSession:
    if not pages:
        raise ValueError("No result pages to merge")
    first = pages[0]
    rows: list[ParsedResultRow] = []
    seen: set[tuple[int, str]] = set()
    for page in pages:
        for row in page.rows:
            key = (row.place, normalize_row_key(row.raw_name))
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    return ParsedIyrSession(
        series_id=first.series_id,
        season_year=first.season_year,
        eid=first.eid,
        category_label=first.category_label,
        race_date=first.race_date,
        results_status=first.results_status,
        results_url=first.results_url,
        rows=rows,
        page_count=len(pages),
    )


def normalize_row_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def parse_results_status(results_status: str) -> str:
    lowered = results_status.lower()
    if "official" in lowered and "unofficial" not in lowered:
        return "official"
    if "unofficial" in lowered:
        return "unofficial"
    return "pending"
