"""Admin routes for Roku discovery and channel launch."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.config import Settings
from raspberry_pab.hdmi import hdmi_connected
from raspberry_pab.models import (
    RokuAutocastUpdate,
    RokuScanResponse,
    RokuStatusResponse,
)
from raspberry_pab.network_info import preferred_lan_base_url
from raspberry_pab.roku_autocast import RokuAutocastWatcher
from raspberry_pab.roku_ecp import launch_channel, send_home
from raspberry_pab.routes.schedule import require_admin_pin

router = APIRouter(prefix="/api/admin/roku", tags=["roku"])


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _watcher(request: Request) -> RokuAutocastWatcher:
    watcher = getattr(request.app.state, "roku_autocast", None)
    if watcher is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Roku support is not initialized",
        )
    return cast(RokuAutocastWatcher, watcher)


@router.get(
    "/status",
    response_model=RokuStatusResponse,
    dependencies=[Depends(require_admin_pin)],
)
async def roku_status(request: Request) -> RokuStatusResponse:
    settings = _settings(request)
    watcher = _watcher(request)
    override = watcher.runtime_enabled_override()
    return RokuStatusResponse(
        hdmi_connected=hdmi_connected(),
        autocast_mode=watcher.effective_mode(),
        autocast_enabled=watcher.should_autocast(),
        autocast_paused=override is False,
        preferred_url=preferred_lan_base_url(settings.port),
        last_error=watcher.last_error,
        devices=watcher.last_devices,
    )


@router.post(
    "/scan",
    response_model=RokuScanResponse,
    dependencies=[Depends(require_admin_pin)],
)
async def roku_scan(request: Request) -> RokuScanResponse:
    settings = _settings(request)
    watcher = _watcher(request)
    devices = await watcher.scan_once()
    override = watcher.runtime_enabled_override()
    return RokuScanResponse(
        devices=devices,
        hdmi_connected=hdmi_connected(),
        autocast_mode=watcher.effective_mode(),
        autocast_enabled=watcher.should_autocast(),
        autocast_paused=override is False,
        preferred_url=preferred_lan_base_url(settings.port),
    )


@router.post("/autocast", dependencies=[Depends(require_admin_pin)])
async def roku_autocast_update(
    request: Request,
    body: RokuAutocastUpdate,
) -> RokuStatusResponse:
    watcher = _watcher(request)
    if body.mode is not None:
        watcher.set_mode(body.mode)
    if body.enabled is not None:
        watcher.set_enabled(body.enabled)
    return await roku_status(request)


@router.post("/{ip}/play", dependencies=[Depends(require_admin_pin)])
async def roku_play(request: Request, ip: str) -> dict[str, object]:
    settings = _settings(request)
    base_url = preferred_lan_base_url(settings.port)
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No LAN address available for Roku deep link",
        )
    try:
        await launch_channel(
            ip,
            channel_id=settings.roku_channel_id,
            content_id=base_url,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to launch Roku channel: {exc}",
        ) from exc
    return {"ok": True, "ip": ip, "content_id": base_url}


@router.post("/{ip}/stop", dependencies=[Depends(require_admin_pin)])
async def roku_stop(ip: str) -> dict[str, object]:
    try:
        await send_home(ip)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send Home to Roku: {exc}",
        ) from exc
    return {"ok": True, "ip": ip}
