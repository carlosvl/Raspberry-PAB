"""HTTP server for the kiosk web UI."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from raspberry_pab.branding import effective_display_title, logo_url
from raspberry_pab.buzzer_controller import BuzzerController
from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.led_controller import LedController
from raspberry_pab.routes.alerts import router as alerts_router
from raspberry_pab.routes.branding import router as branding_router
from raspberry_pab.routes.buzzer import router as buzzer_router
from raspberry_pab.routes.kiosk import router as kiosk_router
from raspberry_pab.routes.led import router as led_router
from raspberry_pab.routes.schedule import router as schedule_router
from raspberry_pab.routes.touch import router as touch_router
from raspberry_pab.scheduler import AlertBroker, ReminderScheduler

logger = logging.getLogger(__name__)


def _local_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        for family, _, _, _, sockaddr in socket.getaddrinfo(socket.gethostname(), None):
            if family == socket.AF_INET:
                address = sockaddr[0]
                if isinstance(address, str) and not address.startswith("127."):
                    addresses.add(address)
    except socket.gaierror:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            address = sock.getsockname()[0]
            if isinstance(address, str) and not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass

    return sorted(addresses)


def create_app(settings: Settings) -> FastAPI:
    """Build the FastAPI app that serves the kiosk UI and API routes."""
    store = ScheduleStore(settings.db_path)
    broker = AlertBroker()
    scheduler = ReminderScheduler(store, broker)
    led_controller = LedController(settings)
    buzzer_controller = BuzzerController(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store.initialize()
        stop_event = asyncio.Event()

        async def hardware_listener() -> None:
            async with broker.subscribe() as queue:
                while not stop_event.is_set():
                    try:
                        alert = await asyncio.wait_for(queue.get(), timeout=0.5)
                    except TimeoutError:
                        continue
                    rule = store.get_rule(alert.rule_id)
                    if rule is None:
                        continue
                    try:
                        await led_controller.flash(rule)
                    except Exception:
                        logger.exception(
                            "LED listener failed for alert %s", alert.id
                        )
                    try:
                        await buzzer_controller.beep(rule)
                    except Exception:
                        logger.exception(
                            "Buzzer listener failed for alert %s", alert.id
                        )

        hardware_task = asyncio.create_task(
            hardware_listener(), name="hardware-alert-listener"
        )
        scheduler.start()
        try:
            yield
        finally:
            stop_event.set()
            hardware_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hardware_task
            await led_controller.shutdown()
            await buzzer_controller.shutdown()
            await scheduler.stop()

    app = FastAPI(
        title=settings.app_name,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.schedule_store = store
    app.state.alert_broker = broker
    app.state.reminder_scheduler = scheduler
    app.state.led_controller = led_controller
    app.state.buzzer_controller = buzzer_controller
    web_dir = settings.web_dir

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    @app.get("/api/config")
    def public_config() -> dict[str, str | int | None]:
        return {
            "app_name": settings.app_name,
            "display_title": effective_display_title(settings, store),
            "logo_url": logo_url(settings, store),
            "port": settings.port,
        }

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    @app.get("/admin")
    def admin() -> FileResponse:
        return FileResponse(web_dir / "admin.html")

    @app.get("/manifest.webmanifest")
    def manifest() -> FileResponse:
        return FileResponse(
            web_dir / "manifest.webmanifest",
            media_type="application/manifest+json",
        )

    @app.get("/sw.js")
    def service_worker() -> FileResponse:
        return FileResponse(web_dir / "sw.js", media_type="text/javascript")

    @app.get("/api/network")
    def network_info() -> dict[str, object]:
        hostname = socket.gethostname()
        return {
            "hostname": hostname,
            "mdns_name": f"{hostname}.local",
            "port": settings.port,
            "urls": [
                f"http://{address}:{settings.port}"
                for address in _local_ipv4_addresses()
            ],
            "hotspot_url": f"http://10.42.0.1:{settings.port}",
        }

    app.include_router(schedule_router)
    app.include_router(branding_router)
    app.include_router(touch_router)
    app.include_router(alerts_router)
    app.include_router(kiosk_router)
    app.include_router(led_router)
    app.include_router(buzzer_router)

    if web_dir.is_dir():
        for subdir in ("css", "js", "assets"):
            path = web_dir / subdir
            if path.is_dir():
                app.mount(f"/{subdir}", StaticFiles(directory=path), name=subdir)

    return app
