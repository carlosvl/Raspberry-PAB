"""API tests for admin buzzer testing."""

from pathlib import Path

from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.server import create_app


def make_web_dir(tmp_path: Path) -> Path:
    root = tmp_path / "web"
    (root / "css").mkdir(parents=True)
    (root / "js").mkdir()
    (root / "index.html").write_text("<html><body>Kiosk</body></html>")
    (root / "admin.html").write_text("<html><body>Admin</body></html>")
    return root


def test_buzzer_test_requires_admin_pin(tmp_path: Path) -> None:
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
        buzzer_enabled=True,
        buzzer_port="/dev/ttyUSB0",
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/admin/buzzer/test",
            json={
                "buzzer_pitch_hz": 2500,
                "buzzer_volume": 80,
                "buzzer_count": 2,
                "buzzer_beep_ms": 200,
                "buzzer_gap_ms": 100,
            },
        )
    assert response.status_code == 401


def test_buzzer_test_requires_configuration(tmp_path: Path) -> None:
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
        buzzer_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/admin/buzzer/test",
            headers={"X-Admin-Pin": "9999"},
            json={
                "buzzer_pitch_hz": 2500,
                "buzzer_volume": 80,
                "buzzer_count": 2,
                "buzzer_beep_ms": 200,
                "buzzer_gap_ms": 100,
            },
        )
    assert response.status_code == 503
