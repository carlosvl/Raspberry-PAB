"""Tests that UI files tell browsers to revalidate after deploys."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.server import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    web_dir = tmp_path / "web"
    (web_dir / "css").mkdir(parents=True)
    (web_dir / "js").mkdir()
    (web_dir / "js" / "kiosk.js").write_text("// board")
    (web_dir / "index.html").write_text("<html></html>")
    (web_dir / "admin.html").write_text("<html></html>")
    (web_dir / "manifest.webmanifest").write_text("{}")
    (web_dir / "sw.js").write_text("")
    settings = Settings(data_dir=tmp_path / "data", web_dir=web_dir)
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.mark.parametrize("path", ["/", "/admin", "/sw.js", "/js/kiosk.js"])
def test_ui_files_require_revalidation(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_unchanged_static_file_returns_304(client: TestClient) -> None:
    first = client.get("/js/kiosk.js")
    etag = first.headers["etag"]
    again = client.get("/js/kiosk.js", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.headers["cache-control"] == "no-cache"
