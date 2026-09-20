"""Tests for Bluetooth admin API and audio sink preference."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from raspberry_pab.audio_sink import resolve_playback_sink
from raspberry_pab.config import Settings
from raspberry_pab.server import create_app


def make_web_dir(tmp_path: Path) -> Path:
    root = tmp_path / "web"
    (root / "css").mkdir(parents=True)
    (root / "js").mkdir()
    (root / "index.html").write_text("<html><body>Kiosk</body></html>")
    (root / "admin.html").write_text("<html><body>Admin</body></html>")
    return root


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    script = tmp_path / "manage-pi-bluetooth.sh"
    script.write_text("#!/bin/bash\n")
    script.chmod(0o755)
    monkeypatch.setattr(
        "raspberry_pab.routes.bluetooth._manage_script",
        lambda: script,
    )
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
    )
    with TestClient(create_app(settings)) as client:
        yield client


def test_bluetooth_status_requires_admin_pin(app_client: TestClient) -> None:
    response = app_client.get("/api/admin/bluetooth/status")
    assert response.status_code == 401


def test_bluetooth_status_ok(
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "raspberry_pab.routes.bluetooth._run_manage",
        lambda *a, timeout=45.0: {
            "powered": True,
            "connected": True,
            "paired": True,
            "trusted": True,
            "mac": "AA:BB:CC:DD:EE:FF",
            "name": "JBL Flip",
            "sink": "bluez_output.aa_bb_cc_dd_ee_ff.a2dp_sink",
        },
    )
    monkeypatch.setattr(
        "raspberry_pab.routes.bluetooth.resolve_playback_sink",
        lambda *_a, **_k: (
            "bluez_output.aa_bb_cc_dd_ee_ff.a2dp_sink",
            "bluetooth",
        ),
    )
    response = app_client.get(
        "/api/admin/bluetooth/status",
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["powered"] is True
    assert payload["mac"] == "AA:BB:CC:DD:EE:FF"
    assert payload["sink_source"] == "bluetooth"
    assert "bluez_output" in (payload["resolved_sink"] or "")


def test_bluetooth_connect_persists_mac(
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "raspberry_pab.routes.bluetooth._run_manage",
        lambda *a, timeout=45.0: {
            "ok": True,
            "mac": "AA:BB:CC:DD:EE:FF",
            "name": "JBL Flip",
            "connected": True,
            "sink": "bluez_output.aa_bb_cc_dd_ee_ff.a2dp_sink",
        },
    )
    response = app_client.post(
        "/api/admin/bluetooth/connect",
        headers={"X-Admin-Pin": "9999"},
        json={"mac": "AA:BB:CC:DD:EE:FF"},
    )
    assert response.status_code == 200
    assert response.json()["mac"] == "AA:BB:CC:DD:EE:FF"

    status = app_client.get(
        "/api/admin/bluetooth/status",
        headers={"X-Admin-Pin": "9999"},
    )
    # status still mocked via _run_manage; preferred_* come from store
    # Re-mock status payload for second call
    monkeypatch.setattr(
        "raspberry_pab.routes.bluetooth._run_manage",
        lambda *a, timeout=45.0: {
            "powered": True,
            "connected": True,
            "paired": True,
            "trusted": True,
            "mac": "AA:BB:CC:DD:EE:FF",
            "name": "JBL Flip",
            "sink": "bluez_output.aa_bb_cc_dd_ee_ff.a2dp_sink",
        },
    )
    monkeypatch.setattr(
        "raspberry_pab.routes.bluetooth.resolve_playback_sink",
        lambda *_a, **_k: (
            "bluez_output.aa_bb_cc_dd_ee_ff.a2dp_sink",
            "bluetooth",
        ),
    )
    status = app_client.get(
        "/api/admin/bluetooth/status",
        headers={"X-Admin-Pin": "9999"},
    )
    assert status.status_code == 200
    assert status.json()["preferred_mac"] == "AA:BB:CC:DD:EE:FF"
    assert status.json()["preferred_name"] == "JBL Flip"


def test_bluetooth_forget_clears_saved(
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "raspberry_pab.routes.bluetooth._run_manage",
        lambda *a, timeout=45.0: {
            "ok": True,
            "mac": "AA:BB:CC:DD:EE:FF",
            "name": "Speaker",
            "connected": True,
            "sink": None,
        },
    )
    app_client.post(
        "/api/admin/bluetooth/connect",
        headers={"X-Admin-Pin": "9999"},
        json={"mac": "AA:BB:CC:DD:EE:FF"},
    )
    monkeypatch.setattr(
        "raspberry_pab.routes.bluetooth._run_manage",
        lambda *a, timeout=45.0: {"ok": True, "forgotten": "AA:BB:CC:DD:EE:FF"},
    )
    response = app_client.post(
        "/api/admin/bluetooth/forget",
        headers={"X-Admin-Pin": "9999"},
        json={"mac": "AA:BB:CC:DD:EE:FF"},
    )
    assert response.status_code == 200

    monkeypatch.setattr(
        "raspberry_pab.routes.bluetooth._run_manage",
        lambda *a, timeout=45.0: {
            "powered": True,
            "connected": False,
            "paired": False,
            "trusted": False,
            "mac": None,
            "name": None,
            "sink": None,
        },
    )
    monkeypatch.setattr(
        "raspberry_pab.routes.bluetooth.resolve_playback_sink",
        lambda *_a, **_k: (None, "none"),
    )
    status = app_client.get(
        "/api/admin/bluetooth/status",
        headers={"X-Admin-Pin": "9999"},
    )
    assert status.json()["preferred_mac"] in (None, "")


def test_bluetooth_script_failure_maps_to_502(
    app_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = MagicMock()
    completed.returncode = 1
    completed.stderr = "Failed to connect"
    completed.stdout = ""
    monkeypatch.setattr(
        "raspberry_pab.routes.bluetooth.subprocess.run",
        lambda *a, **k: completed,
    )
    response = app_client.post(
        "/api/admin/bluetooth/connect",
        headers={"X-Admin-Pin": "9999"},
        json={"mac": "AA:BB:CC:DD:EE:FF"},
    )
    assert response.status_code == 502
    assert "Failed to connect" in response.json()["detail"]


def test_run_manage_parses_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from raspberry_pab.routes import bluetooth as bluetooth_routes

    script = tmp_path / "manage-pi-bluetooth.sh"
    script.write_text("#!/bin/bash\n")
    script.chmod(0o755)
    monkeypatch.setattr(bluetooth_routes, "_manage_script", lambda: script)

    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = json.dumps({"devices": []})
    completed.stderr = ""
    monkeypatch.setattr(
        bluetooth_routes.subprocess,
        "run",
        lambda *a, **k: completed,
    )

    assert bluetooth_routes._run_manage("paired") == {"devices": []}


def test_resolve_playback_sink_prefers_bluez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "raspberry_pab.audio_sink.list_sink_names",
        lambda: [
            "alsa_output.platform-fef00700.hdmi.hdmi-stereo",
            "bluez_output.aa_bb_cc_dd_ee_ff.a2dp_sink",
        ],
    )
    settings = Settings(sound_sink="")
    sink, source = resolve_playback_sink(
        settings,
        preferred_mac="AA:BB:CC:DD:EE:FF",
    )
    assert source == "bluetooth"
    assert sink is not None
    assert "bluez_output" in sink


def test_resolve_playback_sink_override_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "raspberry_pab.audio_sink.list_sink_names",
        lambda: ["bluez_output.aa_bb_cc_dd_ee_ff.a2dp_sink"],
    )
    settings = Settings(sound_sink="custom.sink")
    sink, source = resolve_playback_sink(settings)
    assert sink == "custom.sink"
    assert source == "override"


def test_resolve_playback_sink_falls_back_to_hdmi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "raspberry_pab.audio_sink.list_sink_names",
        lambda: ["alsa_output.platform-fef00700.hdmi.hdmi-stereo"],
    )
    settings = Settings(sound_sink="")
    sink, source = resolve_playback_sink(settings)
    assert source == "hdmi"
    assert sink is not None
    assert "hdmi" in sink.lower()
