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
    led_name: str = "MELKL-OT21 CB"

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
        )
