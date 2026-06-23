"""HTTP server for the kiosk web UI."""

from __future__ import annotations

import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.routes.alerts import router as alerts_router
from raspberry_pab.routes.branding import router as branding_router
from raspberry_pab.routes.kiosk import router as kiosk_router
from raspberry_pab.routes.schedule import router as schedule_router
from raspberry_pab.scheduler import AlertBroker, ReminderScheduler
from raspberry_pab.branding import effective_display_title, logo_url


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

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store.initialize()
        scheduler.start()
        yield
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
    app.include_router(alerts_router)
    app.include_router(kiosk_router)

    if web_dir.is_dir():
        for subdir in ("css", "js", "assets"):
            path = web_dir / subdir
            if path.is_dir():
                app.mount(f"/{subdir}", StaticFiles(directory=path), name=subdir)

    return app
