"""Tests for HDMI sound library API."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.server import create_app

WAV_BYTES = b"RIFF" + b"\x00" * 40


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    web_dir = tmp_path / "web"
    (web_dir / "css").mkdir(parents=True)
    (web_dir / "js").mkdir()
    (web_dir / "index.html").write_text("<html></html>")
    (web_dir / "admin.html").write_text("<html></html>")
    (web_dir / "manifest.webmanifest").write_text("{}")
    (web_dir / "sw.js").write_text("")
    settings = Settings(
        data_dir=tmp_path / "data",
        web_dir=web_dir,
        admin_pin="9999",
        sound_enabled=True,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_upload_list_and_download_sound(client: TestClient) -> None:
    response = client.post(
        "/api/admin/sounds",
        files={"file": ("alert.wav", BytesIO(WAV_BYTES), "audio/wav")},
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 200
    sound = response.json()
    assert sound["original_name"] == "alert.wav"
    assert sound["content_type"] == "audio/wav"
    assert sound["size_bytes"] == len(WAV_BYTES)
    assert sound["stored_name"].endswith(".wav")

    listed = client.get("/api/admin/sounds", headers={"X-Admin-Pin": "9999"})
    assert listed.status_code == 200
    assert any(item["id"] == sound["id"] for item in listed.json())

    downloaded = client.get(
        f"/api/sounds/{sound['id']}",
        headers={"X-Admin-Pin": "9999"},
    )
    assert downloaded.status_code == 200
    assert downloaded.content == WAV_BYTES


def test_upload_rejects_unsupported_type(client: TestClient) -> None:
    response = client.post(
        "/api/admin/sounds",
        files={"file": ("alert.txt", BytesIO(b"hello"), "text/plain")},
        headers={"X-Admin-Pin": "9999"},
    )
    assert response.status_code == 400


def test_delete_sound_rejects_when_in_use(client: TestClient) -> None:
    uploaded = client.post(
        "/api/admin/sounds",
        files={"file": ("alert.wav", BytesIO(WAV_BYTES), "audio/wav")},
        headers={"X-Admin-Pin": "9999"},
    ).json()

    created = client.post(
        "/api/reminder-rules",
        headers={"X-Admin-Pin": "9999"},
        json={
            "offset_minutes": 5,
            "message_template": "Sound {name}",
            "sound_enabled": True,
            "sound_id": uploaded["id"],
            "sound_volume": 70,
        },
    )
    assert created.status_code == 200

    deleted = client.delete(
        f"/api/admin/sounds/{uploaded['id']}",
        headers={"X-Admin-Pin": "9999"},
    )
    assert deleted.status_code == 409


def test_delete_unused_sound(client: TestClient, tmp_path: Path) -> None:
    uploaded = client.post(
        "/api/admin/sounds",
        files={"file": ("alert.wav", BytesIO(WAV_BYTES), "audio/wav")},
        headers={"X-Admin-Pin": "9999"},
    ).json()
    path = tmp_path / "data" / "sounds" / uploaded["stored_name"]
    assert path.is_file()

    deleted = client.delete(
        f"/api/admin/sounds/{uploaded['id']}",
        headers={"X-Admin-Pin": "9999"},
    )
    assert deleted.status_code == 204
    assert not path.exists()


def test_reminder_rule_sound_fields_round_trip(client: TestClient) -> None:
    uploaded = client.post(
        "/api/admin/sounds",
        files={"file": ("alert.wav", BytesIO(WAV_BYTES), "audio/wav")},
        headers={"X-Admin-Pin": "9999"},
    ).json()
    payload = {
        "offset_minutes": 12,
        "message_template": "HDMI {name}",
        "enabled": True,
        "sort_order": 0,
        "sound_enabled": True,
        "sound_id": uploaded["id"],
        "sound_volume": 55,
    }
    created = client.post(
        "/api/reminder-rules",
        headers={"X-Admin-Pin": "9999"},
        json=payload,
    )
    assert created.status_code == 200
    body = created.json()
    assert body["sound_enabled"] is True
    assert body["sound_id"] == uploaded["id"]
    assert body["sound_volume"] == 55

    listed = client.get("/api/reminder-rules")
    saved = next(rule for rule in listed.json() if rule["id"] == body["id"])
    assert saved["sound_id"] == uploaded["id"]
