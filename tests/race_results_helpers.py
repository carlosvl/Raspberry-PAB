"""Helpers for race results tests."""

from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "race_results"


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def fixture_fetcher() -> dict[str, str]:
    return {
        "https://www.precisionrace.com/mca": "precision_race_mca.html",
        "https://www.itsyourrace.com/Results.aspx?id=16915": "iyr_pine_valley_default.html",
        "https://www.itsyourrace.com/results.aspx?id=16915": "iyr_pine_valley_default.html",
    }


def make_fetch_text() -> callable:
    fixtures = fixture_fetcher()

    def fetch_text(url: str) -> str:
        if "id=16915" in url and "eid=137184" in url:
            return load_fixture("iyr_pine_valley_freshman_boys_d2.html")
        normalized = url.split("?")[0].rstrip("/")
        for key, filename in fixtures.items():
            if normalized.lower() == key.split("?")[0].rstrip("/").lower():
                return load_fixture(filename)
        if "id=16915" in url:
            return load_fixture("iyr_pine_valley_default.html")
        raise AssertionError(f"Unexpected fetch URL in test: {url}")

    return fetch_text
