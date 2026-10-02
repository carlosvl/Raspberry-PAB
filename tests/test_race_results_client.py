"""RaceResultsClient picks the browser fingerprint that itsyourrace.com accepts."""

from __future__ import annotations

import pytest

from raspberry_pab.race_results.client import DEFAULT_IMPERSONATE, RaceResultsClient


def test_default_impersonation_is_chrome124() -> None:
    assert DEFAULT_IMPERSONATE == "chrome124"


def test_client_opens_its_session_with_the_default_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    class FakeSession:
        def __init__(self, *, impersonate: str) -> None:
            seen.append(impersonate)

        def close(self) -> None:
            return None

    monkeypatch.setattr("curl_cffi.requests.Session", FakeSession)
    RaceResultsClient().close()
    RaceResultsClient(impersonate="chrome131").close()
    assert seen == ["chrome124", "chrome131"]
