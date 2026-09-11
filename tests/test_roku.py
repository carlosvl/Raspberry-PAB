"""Tests for HDMI detection, Roku discovery/ECP, TV board, and admin Roku API."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.hdmi import hdmi_connected
from raspberry_pab.roku_autocast import RokuAutocastWatcher
from raspberry_pab.roku_discovery import (
    ip_from_location,
    parse_active_app_xml,
    parse_apps_xml,
    parse_device_info_xml,
    parse_ssdp_location,
)
from raspberry_pab.roku_ecp import launch_url
from raspberry_pab.server import create_app


def make_web_dir(tmp_path: Path) -> Path:
    root = tmp_path / "web"
    (root / "css").mkdir(parents=True)
    (root / "js").mkdir()
    (root / "index.html").write_text("<html><body>Kiosk</body></html>")
    (root / "admin.html").write_text("<html><body>Admin</body></html>")
    (root / "manifest.webmanifest").write_text("{}")
    (root / "sw.js").write_text("// sw")
    return root


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
        roku_enabled=True,
        roku_autocast="hdmi-fallback",
    )


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_hdmi_connected_reads_sysfs(tmp_path: Path) -> None:
    connector = tmp_path / "card1-HDMI-A-1"
    connector.mkdir()
    (connector / "status").write_text("connected\n")
    assert hdmi_connected(tmp_path) is True
    (connector / "status").write_text("disconnected\n")
    assert hdmi_connected(tmp_path) is False


def test_hdmi_missing_sysfs(tmp_path: Path) -> None:
    assert hdmi_connected(tmp_path / "missing") is False


def test_parse_ssdp_location() -> None:
    body = (
        b"HTTP/1.1 200 OK\r\n"
        b"CACHE-CONTROL: max-age=3600\r\n"
        b"LOCATION: http://192.168.1.50:8060/\r\n"
        b"ST: roku:ecp\r\n"
        b"\r\n"
    )
    assert parse_ssdp_location(body) == "http://192.168.1.50:8060/"
    assert ip_from_location("http://192.168.1.50:8060/") == "192.168.1.50"


def test_parse_device_and_apps_xml() -> None:
    info = parse_device_info_xml(
        """
        <device-info>
          <friendly-device-name>Clubhouse TV</friendly-device-name>
          <model-name>Roku Ultra</model-name>
          <serial-number>ABC123</serial-number>
        </device-info>
        """
    )
    assert info["friendly_name"] == "Clubhouse TV"
    assert info["model_name"] == "Roku Ultra"
    apps = """
    <apps>
      <app id="12" type="appl">Netflix</app>
      <app id="dev" type="appl">Raspberry-PAB</app>
    </apps>
    """
    assert parse_apps_xml(apps, "dev") is True
    assert parse_apps_xml("<apps><app id=\"12\">Netflix</app></apps>", "dev") is False
    app_id, app_name = parse_active_app_xml(
        '<active-app><app id="dev">Raspberry-PAB</app></active-app>'
    )
    assert app_id == "dev"
    assert app_name == "Raspberry-PAB"


def test_launch_url_encodes_content_id() -> None:
    url = launch_url(
        "192.168.1.50",
        channel_id="dev",
        content_id="http://10.42.0.1:8080",
    )
    assert url.startswith("http://192.168.1.50:8060/launch/dev?contentId=")
    assert "http%3A%2F%2F10.42.0.1%3A8080" in url


def test_autocast_hdmi_fallback(tmp_path: Path, settings: Settings) -> None:
    store = MagicMock()
    store.get_setting.return_value = None
    watcher = RokuAutocastWatcher(settings, store)
    assert watcher.should_autocast(hdmi_is_connected=False) is True
    assert watcher.should_autocast(hdmi_is_connected=True) is False

    store.get_setting.side_effect = lambda key: {
        "roku_autocast_mode": "on",
    }.get(key)
    assert watcher.should_autocast(hdmi_is_connected=True) is True

    store.get_setting.side_effect = lambda key: {
        "roku_autocast_enabled": "false",
        "roku_autocast_mode": "on",
    }.get(key)
    assert watcher.should_autocast(hdmi_is_connected=False) is False


def test_tv_board_public(client: TestClient) -> None:
    create = client.post(
        "/api/participants",
        headers={"X-Admin-Pin": "9999"},
        json={
            "name": "Carlos",
            "event_date": date.today().isoformat(),
            "start_time": "11:00:00",
            "race": "Pro Men",
            "call_up": "Staging",
        },
    )
    assert create.status_code == 200
    response = client.get("/api/tv-board")
    assert response.status_code == 200
    payload = response.json()
    assert payload["display_title"]
    assert payload["display_date"]
    assert payload["kiosk_now"]
    assert isinstance(payload["participants"], list)
    assert payload["participants"][0]["name"] == "Carlos"
    assert "lan_urls" in payload
    assert payload["poll_seconds"] == 2
    assert payload["active_alert"] is None


def test_roku_admin_requires_pin(client: TestClient) -> None:
    assert client.get("/api/admin/roku/status").status_code == 401
    assert client.post("/api/admin/roku/scan").status_code == 401


def test_roku_status_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("raspberry_pab.routes.roku.hdmi_connected", lambda: False)
    monkeypatch.setattr(
        "raspberry_pab.routes.roku.preferred_lan_base_url",
        lambda _port: "http://192.168.1.10:8080",
    )
    response = client.get(
        "/api/admin/roku/status",
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["hdmi_connected"] is False
    assert payload["autocast_mode"] == "hdmi-fallback"
    assert payload["preferred_url"] == "http://192.168.1.10:8080"
    assert payload["autocast_paused"] is False


def test_roku_scan_and_play(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from raspberry_pab.models import RokuDevice

    device = RokuDevice(
        ip="192.168.1.50",
        friendly_name="Clubhouse",
        has_pab_channel=True,
    )

    async def fake_scan(self: RokuAutocastWatcher) -> list[RokuDevice]:
        self._last_devices = [device]
        return [device]

    monkeypatch.setattr(RokuAutocastWatcher, "scan_once", fake_scan)
    monkeypatch.setattr(
        "raspberry_pab.routes.roku.preferred_lan_base_url",
        lambda _port: "http://192.168.1.10:8080",
    )
    launch = AsyncMock()
    home = AsyncMock()
    monkeypatch.setattr("raspberry_pab.routes.roku.launch_channel", launch)
    monkeypatch.setattr("raspberry_pab.routes.roku.send_home", home)

    scan = client.post(
        "/api/admin/roku/scan",
        headers={"X-Admin-Pin": "9999"},
    )
    assert scan.status_code == 200
    assert scan.json()["devices"][0]["ip"] == "192.168.1.50"

    play = client.post(
        "/api/admin/roku/192.168.1.50/play",
        headers={"X-Admin-Pin": "9999"},
    )
    assert play.status_code == 200
    launch.assert_awaited_once()
    assert launch.await_args.kwargs["content_id"] == "http://192.168.1.10:8080"

    stop = client.post(
        "/api/admin/roku/192.168.1.50/stop",
        headers={"X-Admin-Pin": "9999"},
    )
    assert stop.status_code == 200
    home.assert_awaited_once()


def test_roku_autocast_update(client: TestClient) -> None:
    response = client.post(
        "/api/admin/roku/autocast",
        headers={"X-Admin-Pin": "9999"},
        json={"mode": "off", "enabled": False},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["autocast_mode"] == "off"
    assert payload["autocast_paused"] is True
    assert payload["autocast_enabled"] is False


def test_settings_roku_from_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PAB_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PAB_WEB_DIR", str(make_web_dir(tmp_path)))
    monkeypatch.setenv("PAB_ROKU_AUTOCAST", "on")
    monkeypatch.setenv("PAB_ROKU_ENABLED", "false")
    settings = Settings.from_env()
    assert settings.roku_autocast == "on"
    assert settings.roku_enabled is False
