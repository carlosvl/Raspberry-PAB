"""Discover and fetch official MCA result PDFs from the results archive page."""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urljoin

from bs4 import BeautifulSoup

ARCHIVE_URL = "https://minnesotacycling.org/results-archive/"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "raspberry-pab" / "mca"

DocKind = Literal["standings", "individual_results", "team_scores", "other"]
Level = Literal["HS", "MS"]

_THROUGH_RACE = re.compile(r"through[\s\-]+Race[\s\-]+(\d+[AB]?)", re.IGNORECASE)
_RACE_LABEL = re.compile(r"Race[\s#\-]*(\d+[AB]?)\b", re.IGNORECASE)
_SEASON_HEADING = re.compile(r"^\s*(\d{4})\s+Results\b", re.IGNORECASE)


@dataclass(frozen=True)
class ArchiveDoc:
    kind: DocKind
    title: str
    url: str
    race_label: str | None
    level: Level | None
    through_race: str | None


def _level_of(text: str) -> Level | None:
    lowered = text.lower()
    if re.search(r"\bhs\b|high[\s\-]school", lowered):
        return "HS"
    if re.search(r"\bms\b|middle[\s\-]school", lowered):
        return "MS"
    return None


def classify_doc(title: str, url: str) -> ArchiveDoc:
    """Classify one archive link by its text and file name."""
    filename = url.rsplit("/", 1)[-1]
    text = f"{title} {filename.replace('-', ' ').replace('_', ' ')}"
    lowered = text.lower()
    kind: DocKind
    if not url.lower().endswith(".pdf"):
        kind = "other"
    elif "individual scores" in lowered or "individual points" in lowered:
        kind = "standings"
    elif "team" in lowered and "score" in lowered:
        kind = "team_scores"
    elif "result" in lowered:
        kind = "individual_results"
    else:
        kind = "other"
    through = _THROUGH_RACE.search(text)
    race = _RACE_LABEL.search(title) or _RACE_LABEL.search(text)
    return ArchiveDoc(
        kind=kind,
        title=title.strip(),
        url=url,
        race_label=race.group(1).upper() if race else None,
        level=_level_of(text) if kind in ("standings", "team_scores") else None,
        through_race=through.group(1).upper() if through else None,
    )


def parse_results_archive(
    html: str,
    *,
    season: int,
    base_url: str = ARCHIVE_URL,
) -> list[ArchiveDoc]:
    """Return the PDF links listed under the ``<season> Results`` heading."""
    soup = BeautifulSoup(html, "html.parser")
    heading = None
    for h2 in soup.find_all("h2"):
        match = _SEASON_HEADING.match(h2.get_text(" ", strip=True))
        if match is not None and int(match.group(1)) == season:
            heading = h2
            break
    if heading is None:
        return []
    docs: list[ArchiveDoc] = []
    for element in heading.find_all_next(["h2", "a"]):
        if element.name == "h2":
            break
        href = element.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        doc = classify_doc(element.get_text(" ", strip=True), urljoin(base_url, href))
        if doc.kind != "other":
            docs.append(doc)
    return docs


def _race_sort_key(label: str | None) -> tuple[int, str]:
    if not label:
        return (-1, "")
    match = re.match(r"(\d+)([AB]?)", label)
    if match is None:
        return (-1, label)
    return (int(match.group(1)), match.group(2))


def latest_standings(docs: list[ArchiveDoc], level: Level) -> ArchiveDoc | None:
    """Pick the standings PDF that covers the most races (later link wins ties)."""
    candidates = [d for d in docs if d.kind == "standings" and d.level == level]
    if not candidates:
        return None
    best = candidates[0]
    for doc in candidates[1:]:
        if _race_sort_key(doc.through_race) >= _race_sort_key(best.through_race):
            best = doc
    return best


def pdf_bytes_to_text(data: bytes) -> str:
    """Extract text with column spacing preserved (``pypdf`` layout mode)."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(
        page.extract_text(extraction_mode="layout") for page in reader.pages
    )


def fetch_bytes(url: str) -> bytes:
    from curl_cffi import requests as curl_requests

    response = curl_requests.get(url, impersonate="chrome131", timeout=60)
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code} for {url}")
    return bytes(response.content)


def fetch_pdf_text(
    url: str,
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    refresh: bool = False,
) -> str:
    """Download (or reuse the cached copy of) a PDF and return its text."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    path = cache_dir / f"{digest}-{url.rsplit('/', 1)[-1]}"
    if refresh or not path.exists():
        path.write_bytes(fetch_bytes(url))
    return pdf_bytes_to_text(path.read_bytes())
