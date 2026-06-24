"""API tests for admin LED strip testing."""

import asyncio
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

from raspberry_pab.config import Settings
from raspberry_pab.led_controller import LedController
from raspberry_pab.server import create_app


def make_web_dir(tmp_path: Path) -> Path:
    root = tmp_path / "web"
    (root / "css").mkdir(parents=True)
    (root / "js").mkdir()
    (root / "index.html").write_text("<html><body>Kiosk</body></html>")
    (root / "admin.html").write_text("<html><body>Admin</body></html>")
    return root


def test_led_test_requires_admin_pin(tmp_path: Path) -> None:
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
        led_enabled=True,
        led_address="BE:28:79:00:06:CB",
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/admin/led/test",
            json={
                "led_red": 255,
                "led_green": 200,
                "led_blue": 0,
                "led_flash_interval_ms": 500,
                "led_flash_duration_seconds": 2,
            },
        )
    assert response.status_code == 401


def test_led_test_requires_configuration(tmp_path: Path) -> None:
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
        led_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/admin/led/test",
            headers={"X-Admin-Pin": "9999"},
            json={
                "led_red": 255,
                "led_green": 200,
                "led_blue": 0,
                "led_flash_interval_ms": 500,
                "led_flash_duration_seconds": 2,
            },
        )
    assert response.status_code == 503


def test_led_test_triggers_controller(tmp_path: Path) -> None:
    settings = Settings(
        admin_pin="9999",
        data_dir=tmp_path / "data",
        web_dir=make_web_dir(tmp_path),
        led_enabled=True,
        led_address="BE:28:79:00:06:CB",
    )
    calls: list[tuple[int, int, int]] = []

    class MockLamp:
        async def connect(self) -> None:
            return None

        async def disconnect(self) -> None:
            return None

        async def set_rgb(self, red: int, green: int, blue: int) -> None:
            calls.append((red, green, blue))

        async def power_on(self) -> None:
            return None

        async def set_animation(self, mode: int) -> None:
            return None

        async def set_speed(self, speed: int) -> None:
            return None

        async def power_off(self) -> None:
            return None

    async def factory(_settings: Settings) -> MockLamp:
        return MockLamp()

    with TestClient(create_app(settings)) as client:
        controller = cast(LedController, client.app.state.led_controller)
        controller._lamp_factory = factory  # noqa: SLF001
        response = client.post(
            "/api/admin/led/test",
            headers={"X-Admin-Pin": "9999"},
            json={
                "led_red": 10,
                "led_green": 20,
                "led_blue": 30,
                "led_flash_interval_ms": 200,
                "led_flash_duration_seconds": 1,
                "led_chase_duration_seconds": 0,
            },
        )

        async def wait_for_flash() -> None:
            if controller._flash_task is not None:
                await controller._flash_task

        client.portal.call(wait_for_flash)

    assert response.status_code == 200
    assert response.json() == {"testing": True}
    assert calls
