"""HTTP client for race results scraping."""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

DEFAULT_USER_AGENT = "Raspberry-PAB/0.1 (+https://github.com/carlosvl/Raspberry-PAB)"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MIN_INTERVAL = 1.0


class RaceResultsClient:
    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
            transport=transport,
        )
        self._min_interval = min_interval
        self._last_fetch = 0.0

    def close(self) -> None:
        self._client.close()

    def fetch_text(self, url: str) -> str:
        elapsed = time.monotonic() - self._last_fetch
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        response = self._client.get(url)
        response.raise_for_status()
        self._last_fetch = time.monotonic()
        return response.text


FetchText = Callable[[str], str]
