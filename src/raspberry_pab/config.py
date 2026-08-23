"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "raspberry-pab"
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_BIND_HOST = "0.0.0.0"
_DEFAULT_PORT = 8080


def _default_web_dir() -> Path:
    cwd_web = Path.cwd() / "web"
    if cwd_web.is_dir():
        return cwd_web
    return Path(__file__).resolve().parents[3] / "web"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the kiosk application."""

    app_name: str = "Raspberry-PAB"
    display_title: str = "Raspberry-PAB"
    log_level: str = "INFO"
    admin_pin: str = "1234"
    data_dir: Path = _DEFAULT_DATA_DIR
    host: str = _DEFAULT_HOST
    bind_host: str = _DEFAULT_BIND_HOST
    port: int = _DEFAULT_PORT
    web_dir: Path = Path(_default_web_dir())
    led_enabled: bool = False
    led_address: str = ""
    led_name: str = "MELK-OT21   CB"
    buzzer_enabled: bool = False
    buzzer_port: str = ""
    buzzer_mode: str = "active"
    buzzer_baud: int = 115200
    matrix_enabled: bool = False
    matrix_port: str = ""
    matrix_width: int = 96  # three daisy-chained 8x32 panels (ESP32)
    matrix_height: int = 8
    matrix_brightness: int = 64
    matrix_baud: int = 115200

    @property
    def kiosk_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "schedule.db"

    @property
    def logo_path(self) -> Path:
        return self.data_dir / "logo.png"

    @classmethod
    def from_env(cls) -> Settings:
        data_dir = Path(os.getenv("PAB_DATA_DIR", str(_DEFAULT_DATA_DIR)))
        web_dir = Path(os.getenv("PAB_WEB_DIR", str(_default_web_dir())))
        port = int(os.getenv("PAB_PORT", str(_DEFAULT_PORT)))
        return cls(
            app_name=os.getenv("PAB_APP_NAME", cls.app_name),
            display_title=os.getenv(
                "PAB_DISPLAY_TITLE",
                os.getenv("PAB_APP_NAME", cls.app_name),
            ),
            log_level=os.getenv("PAB_LOG_LEVEL", cls.log_level),
            admin_pin=os.getenv("PAB_ADMIN_PIN", cls.admin_pin),
            data_dir=data_dir,
            host=os.getenv("PAB_HOST", _DEFAULT_HOST),
            bind_host=os.getenv("PAB_BIND_HOST", _DEFAULT_BIND_HOST),
            port=port,
            web_dir=web_dir,
            led_enabled=_env_bool("PAB_LED_ENABLED", cls.led_enabled),
            led_address=os.getenv("PAB_LED_ADDRESS", cls.led_address),
            led_name=os.getenv("PAB_LED_NAME", cls.led_name),
            buzzer_enabled=_env_bool("PAB_BUZZER_ENABLED", cls.buzzer_enabled),
            buzzer_port=os.getenv("PAB_BUZZER_PORT", cls.buzzer_port),
            buzzer_mode=os.getenv("PAB_BUZZER_MODE", cls.buzzer_mode),
            buzzer_baud=int(os.getenv("PAB_BUZZER_BAUD", str(cls.buzzer_baud))),
            matrix_enabled=_env_bool("PAB_MATRIX_ENABLED", cls.matrix_enabled),
            matrix_port=os.getenv("PAB_MATRIX_PORT", cls.matrix_port),
            matrix_width=int(os.getenv("PAB_MATRIX_WIDTH", str(cls.matrix_width))),
            matrix_height=int(
                os.getenv("PAB_MATRIX_HEIGHT", str(cls.matrix_height))
            ),
            matrix_brightness=int(
                os.getenv("PAB_MATRIX_BRIGHTNESS", str(cls.matrix_brightness))
            ),
            matrix_baud=int(os.getenv("PAB_MATRIX_BAUD", str(cls.matrix_baud))),
        )
