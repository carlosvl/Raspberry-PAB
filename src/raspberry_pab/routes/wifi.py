"""Local admin routes for Wi-Fi management via NetworkManager."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raspberry_pab.models import (
    WifiConnectRequest,
    WifiConnectResponse,
    WifiConnectSavedRequest,
    WifiForgetResponse,
    WifiSavedNetworksResponse,
    WifiScanResponse,
    WifiStatus,
)
from raspberry_pab.routes.schedule import require_admin_pin

router = APIRouter(prefix="/api/admin/wifi", tags=["wifi"])

HOTSPOT_CONNECTION = "PAB-Hotspot"


def _require_local_client(request: Request) -> None:
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wi-Fi controls are only available on the local kiosk display",
        )


def _manage_script() -> Path:
    installed = Path.home() / "bin" / "manage-pi-wifi.sh"
    if installed.is_file():
        return installed
    return Path(__file__).resolve().parents[3] / "scripts" / "manage-pi-wifi.sh"


def _run_manage(
    *args: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    script = _manage_script()
    if not script.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Wi-Fi manage script is not installed",
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
            detail="Wi-Fi command timed out",
        ) from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "Wi-Fi command failed").strip()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail[:500],
        )

    stdout = (completed.stdout or "").strip()
    if not stdout:
        return {}
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Wi-Fi script returned invalid JSON: {stdout[:200]}",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Wi-Fi script returned unexpected JSON",
        )
    return payload


@router.get(
    "/status",
    response_model=WifiStatus,
    dependencies=[Depends(require_admin_pin)],
)
def wifi_status(request: Request) -> WifiStatus:
    _require_local_client(request)
    payload = _run_manage("status", timeout=10.0)
    return WifiStatus(**payload)


@router.get(
    "/saved",
    response_model=WifiSavedNetworksResponse,
    dependencies=[Depends(require_admin_pin)],
)
def wifi_saved(request: Request) -> WifiSavedNetworksResponse:
    _require_local_client(request)
    payload = _run_manage("saved", timeout=15.0)
    return WifiSavedNetworksResponse(**payload)


@router.post(
    "/scan",
    response_model=WifiScanResponse,
    dependencies=[Depends(require_admin_pin)],
)
def wifi_scan(request: Request) -> WifiScanResponse:
    _require_local_client(request)
    payload = _run_manage("scan", timeout=25.0)
    return WifiScanResponse(**payload)


@router.post(
    "/connect",
    response_model=WifiConnectResponse,
    dependencies=[Depends(require_admin_pin)],
)
def wifi_connect(request: Request, body: WifiConnectRequest) -> WifiConnectResponse:
    _require_local_client(request)
    args = ["connect", body.ssid]
    if body.password:
        args.append(body.password)
    payload = _run_manage(*args, timeout=45.0)
    return WifiConnectResponse(**payload)


@router.post(
    "/connect-saved",
    response_model=WifiConnectResponse,
    dependencies=[Depends(require_admin_pin)],
)
def wifi_connect_saved(
    request: Request,
    body: WifiConnectSavedRequest,
) -> WifiConnectResponse:
    _require_local_client(request)
    if body.name == HOTSPOT_CONNECTION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot activate the fallback hotspot profile from this control",
        )
    payload = _run_manage("connect-saved", body.name, timeout=45.0)
    return WifiConnectResponse(**payload)


@router.delete(
    "/saved/{name}",
    response_model=WifiForgetResponse,
    dependencies=[Depends(require_admin_pin)],
)
def wifi_forget(request: Request, name: str) -> WifiForgetResponse:
    _require_local_client(request)
    decoded = unquote(name)
    if decoded == HOTSPOT_CONNECTION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refusing to delete the fallback hotspot profile",
        )
    payload = _run_manage("forget", decoded, timeout=15.0)
    return WifiForgetResponse(**payload)
