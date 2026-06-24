"""Core application logic."""

from __future__ import annotations

import logging

import uvicorn

from raspberry_pab.config import Settings
from raspberry_pab.server import create_app

logger = logging.getLogger(__name__)


class Application:
    """Kiosk backend: serves the fullscreen web UI and remote admin."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()

    def run(self) -> int:
        """Start the web server. Returns process exit code."""
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)

        if not self.settings.web_dir.is_dir():
            logger.error("Web directory not found: %s", self.settings.web_dir)
            return 1

        logger.info(
            "Starting kiosk server: %s (bind %s)",
            self.settings.kiosk_url,
            self.settings.bind_host,
        )
        logger.info("Web root: %s", self.settings.web_dir)
        logger.info("Data directory: %s", self.settings.data_dir)

        app = create_app(self.settings)
        uvicorn.run(
            app,
            host=self.settings.bind_host,
            port=self.settings.port,
            log_level=self.settings.log_level.lower(),
            timeout_graceful_shutdown=5,
        )
        return 0
