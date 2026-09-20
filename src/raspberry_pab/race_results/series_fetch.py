"""Fetch all ITS YOUR RACE category result sessions for a series URL."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from raspberry_pab.race_results.client import FetchText, RaceResultsClient
from raspberry_pab.race_results.itsyourrace import (
    ParsedIyrSession,
    build_results_url,
    build_series_landing_url,
    merge_result_pages,
    parse_category_options,
    parse_results_page_html,
)
from raspberry_pab.race_results.precision_race import (
    build_iyr_base_url,
    extract_iyr_series_id,
)


@dataclass(frozen=True)
class SeriesFetchResult:
    series_id: str
    base_url: str
    season_year: int
    landing_url: str
    sessions: list[ParsedIyrSession]
    skipped_categories: list[str]


def parse_series_url(url: str) -> tuple[str, str, int | None]:
    """Return (base_url, series_id, season_year_or_None)."""
    series_id = extract_iyr_series_id(url)
    base_url = build_iyr_base_url(url)
    query = parse_qs(urlparse(url).query)
    year_raw = query.get("y", [None])[0]
    season_year = int(year_raw) if year_raw and str(year_raw).isdigit() else None
    return base_url, series_id, season_year


def _detect_season_year(html: str, fallback: int | None) -> int:
    if fallback is not None:
        return fallback
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select", id="ddlYear")
    if select is not None:
        selected = select.find("option", selected=True)
        if selected is not None:
            selected_value = str(selected.get("value") or "").strip()
            if selected_value.isdigit():
                return int(selected_value)
        for option in select.find_all("option"):
            value = str(option.get("value") or "").strip()
            if value.isdigit():
                return int(value)
    raise ValueError("Could not detect season year from IYR landing page")


def fetch_series_sessions(
    url: str,
    *,
    fetch_text: FetchText | None = None,
) -> SeriesFetchResult:
    owned: RaceResultsClient | None = None
    if fetch_text is None:
        owned = RaceResultsClient()
        fetch_text = owned.fetch_text
    try:
        base_url, series_id, year_hint = parse_series_url(url)
        landing_url = build_series_landing_url(base_url=base_url, series_id=series_id)
        landing_html = fetch_text(landing_url)
        season_year = _detect_season_year(landing_html, year_hint)
        categories = parse_category_options(landing_html)
        sessions: list[ParsedIyrSession] = []
        skipped: list[str] = []
        for category in categories:
            first_page_url = build_results_url(
                base_url=base_url,
                series_id=series_id,
                season_year=season_year,
                eid=category.eid,
                page=1,
            )
            first_page_html = fetch_text(first_page_url)
            try:
                first_page = parse_results_page_html(
                    first_page_html,
                    results_url=first_page_url,
                    series_id=series_id,
                    season_year=season_year,
                    eid=category.eid,
                )
            except ValueError:
                skipped.append(category.label)
                continue
            pages = [first_page]
            for page_number in range(2, first_page.page_count + 1):
                page_url = build_results_url(
                    base_url=base_url,
                    series_id=series_id,
                    season_year=season_year,
                    eid=category.eid,
                    page=page_number,
                )
                page_html = fetch_text(page_url)
                pages.append(
                    parse_results_page_html(
                        page_html,
                        results_url=page_url,
                        series_id=series_id,
                        season_year=season_year,
                        eid=category.eid,
                    )
                )
            sessions.append(merge_result_pages(pages))
        return SeriesFetchResult(
            series_id=series_id,
            base_url=base_url,
            season_year=season_year,
            landing_url=landing_url,
            sessions=sessions,
            skipped_categories=skipped,
        )
    finally:
        if owned is not None:
            owned.close()
