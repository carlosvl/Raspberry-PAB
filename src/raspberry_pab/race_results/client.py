"""HTTP client for race results scraping."""

from __future__ import annotations

import time
from collections.abc import Callable

DEFAULT_USER_AGENT = "Raspberry-PAB/0.1 (+https://github.com/carlosvl/Raspberry-PAB)"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MIN_INTERVAL = 1.0
DEFAULT_IMPERSONATE = "chrome131"


class RaceResultsClient:
    """Fetch race-results HTML.

    Uses curl_cffi Chrome impersonation because Cloudflare on itsyourrace.com
    blocks plain httpx/urllib TLS fingerprints with a JS challenge (403).
    """

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        impersonate: str = DEFAULT_IMPERSONATE,
    ) -> None:
        from curl_cffi import requests as curl_requests

        self._session = curl_requests.Session(impersonate=impersonate)
        self._user_agent = user_agent
        self._timeout = timeout
        self._min_interval = min_interval
        self._impersonate = impersonate
        self._last_fetch = 0.0

    def close(self) -> None:
        close = getattr(self._session, "close", None)
        if callable(close):
            close()

    def fetch_text(self, url: str) -> str:
        elapsed = time.monotonic() - self._last_fetch
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        response = self._session.get(
            url,
            timeout=self._timeout,
            allow_redirects=True,
            headers={"User-Agent": self._user_agent},
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"HTTP {response.status_code} for {url} (curl_cffi/{self._impersonate})"
            )
        self._last_fetch = time.monotonic()
        return response.text or ""


FetchText = Callable[[str], str]
