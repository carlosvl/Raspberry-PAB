"""Admin routes for Bluetooth speaker scan / pair / connect."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.audio_sink import (
    BT_SPEAKER_MAC_KEY,
    BT_SPEAKER_NAME_KEY,
    resolve_playback_sink,
)
from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import (
    BluetoothActionResponse,
    BluetoothDevicesResponse,
    BluetoothMacRequest,
    BluetoothStatus,
)
from raspberry_pab.routes.schedule import require_admin_pin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/bluetooth", tags=["bluetooth"])


def _store(request: Request) -> ScheduleStore:
    return cast(ScheduleStore, request.app.state.schedule_store)


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _manage_script() -> Path:
    installed = Path.home() / "bin" / "manage-pi-bluetooth.sh"
    if installed.is_file():
        return installed
    return Path(__file__).resolve().parents[3] / "scripts" / "manage-pi-bluetooth.sh"


def _run_manage(*args: str, timeout: float = 45.0) -> dict[str, Any]:
    script = _manage_script()
    if not script.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bluetooth manage script is not installed",
        )
    command = ["sudo", "-n", str(script), *args]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Bluetooth command timed out",
        ) from exc

    if completed.returncode != 0:
        detail = (
            completed.stderr or completed.stdout or "Bluetooth command failed"
        ).strip()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail[:500],
        )

    stdout = (completed.stdout or "").strip()
    if not stdout:
        return {}
    import json

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Bluetooth script returned invalid JSON: {stdout[:200]}",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Bluetooth script returned unexpected JSON",
        )
    return payload


def _preferred(store: ScheduleStore) -> tuple[str | None, str | None]:
    mac = store.get_setting(BT_SPEAKER_MAC_KEY)
    name = store.get_setting(BT_SPEAKER_NAME_KEY)
    return (mac or None, name or None)


@router.get(
    "/status",
    response_model=BluetoothStatus,
    dependencies=[Depends(require_admin_pin)],
)
def bluetooth_status(request: Request) -> BluetoothStatus:
    settings = _settings(request)
    store = _store(request)
    preferred_mac, preferred_name = _preferred(store)
    payload = _run_manage("status", "--json")
    sink, source = resolve_playback_sink(settings, preferred_mac=preferred_mac)
    return BluetoothStatus(
        powered=bool(payload.get("powered")),
        connected=bool(payload.get("connected")),
        paired=bool(payload.get("paired")),
        trusted=bool(payload.get("trusted")),
        mac=payload.get("mac"),
        name=payload.get("name"),
        sink=payload.get("sink"),
        preferred_mac=preferred_mac,
        preferred_name=preferred_name,
        resolved_sink=sink,
        sink_source=source,
    )


@router.get(
    "/paired",
    response_model=BluetoothDevicesResponse,
    dependencies=[Depends(require_admin_pin)],
)
def bluetooth_paired() -> BluetoothDevicesResponse:
    payload = _run_manage("paired", "--json")
    return BluetoothDevicesResponse(devices=payload.get("devices") or [])


@router.post(
    "/scan",
    response_model=BluetoothDevicesResponse,
    dependencies=[Depends(require_admin_pin)],
)
def bluetooth_scan() -> BluetoothDevicesResponse:
    payload = _run_manage("scan", "--json", timeout=60.0)
    return BluetoothDevicesResponse(devices=payload.get("devices") or [])


@router.post(
    "/pair",
    response_model=BluetoothActionResponse,
    dependencies=[Depends(require_admin_pin)],
)
def bluetooth_pair(body: BluetoothMacRequest) -> BluetoothActionResponse:
    payload = _run_manage("pair", body.mac.strip(), timeout=60.0)
    return BluetoothActionResponse(
        ok=bool(payload.get("ok", True)),
        mac=payload.get("mac") or body.mac,
        paired=payload.get("paired"),
        trusted=payload.get("trusted"),
    )


@router.post(
    "/connect",
    response_model=BluetoothActionResponse,
    dependencies=[Depends(require_admin_pin)],
)
def bluetooth_connect(
    request: Request,
    body: BluetoothMacRequest,
) -> BluetoothActionResponse:
    store = _store(request)
    payload = _run_manage("connect", body.mac.strip(), timeout=60.0)
    mac = str(payload.get("mac") or body.mac).strip()
    name = payload.get("name")
    store.set_setting(BT_SPEAKER_MAC_KEY, mac)
    if name:
        store.set_setting(BT_SPEAKER_NAME_KEY, str(name))
    return BluetoothActionResponse(
        ok=bool(payload.get("ok", True)),
        mac=mac,
        name=str(name) if name else None,
        connected=True,
        sink=payload.get("sink"),
    )


@router.post(
    "/disconnect",
    response_model=BluetoothActionResponse,
    dependencies=[Depends(require_admin_pin)],
)
def bluetooth_disconnect() -> BluetoothActionResponse:
    payload = _run_manage("disconnect", timeout=30.0)
    return BluetoothActionResponse(
        ok=bool(payload.get("ok", True)),
        mac=payload.get("mac"),
        disconnected=True,
    )


@router.post(
    "/forget",
    response_model=BluetoothActionResponse,
    dependencies=[Depends(require_admin_pin)],
)
def bluetooth_forget(
    request: Request,
    body: BluetoothMacRequest,
) -> BluetoothActionResponse:
    store = _store(request)
    payload = _run_manage("forget", body.mac.strip(), timeout=30.0)
    preferred_mac, _ = _preferred(store)
    forgotten = str(payload.get("forgotten") or body.mac).strip()
    if preferred_mac and preferred_mac.upper() == forgotten.upper():
        store.set_setting(BT_SPEAKER_MAC_KEY, "")
        store.set_setting(BT_SPEAKER_NAME_KEY, "")
    return BluetoothActionResponse(
        ok=bool(payload.get("ok", True)),
        forgotten=forgotten,
    )


async def try_reconnect_saved_speaker(store: ScheduleStore) -> None:
    """Best-effort reconnect of the last Admin-connected speaker on boot."""
    mac = store.get_setting(BT_SPEAKER_MAC_KEY)
    if not mac or not mac.strip():
        return
    try:
        payload = _run_manage("connect", mac.strip(), timeout=45.0)
        logger.info(
            "Bluetooth reconnect attempted for %s (sink=%s)",
            mac,
            payload.get("sink"),
        )
    except Exception:
        logger.info("Bluetooth reconnect skipped/failed for %s", mac, exc_info=True)
