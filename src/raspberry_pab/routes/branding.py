"""Admin branding routes for kiosk title and logo."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response

from raspberry_pab.branding import (
    DISPLAY_TITLE_KEY,
    LOGO_UPDATED_AT_KEY,
    MAX_LOGO_BYTES,
    PNG_SIGNATURE,
    branding_response,
)
from raspberry_pab.models import BrandingResponse, BrandingUpdate
from raspberry_pab.routes.schedule import get_settings, get_store, require_admin_pin

router = APIRouter(prefix="/api", tags=["branding"])


@router.get("/branding/logo")
def serve_logo(request: Request) -> FileResponse:
    settings = get_settings(request)
    logo_path = settings.logo_path
    if not logo_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Logo not found",
        )
    return FileResponse(logo_path, media_type="image/png")


@router.get(
    "/admin/branding",
    response_model=BrandingResponse,
    dependencies=[Depends(require_admin_pin)],
)
def get_branding(request: Request) -> BrandingResponse:
    settings = get_settings(request)
    store = get_store(request)
    return branding_response(settings, store)


@router.put(
    "/admin/branding",
    response_model=BrandingResponse,
    dependencies=[Depends(require_admin_pin)],
)
def update_branding(request: Request, update: BrandingUpdate) -> BrandingResponse:
    settings = get_settings(request)
    store = get_store(request)
    store.set_setting(DISPLAY_TITLE_KEY, update.display_title.strip())
    return branding_response(settings, store)


@router.post(
    "/admin/branding/logo",
    response_model=BrandingResponse,
    dependencies=[Depends(require_admin_pin)],
)
async def upload_logo(
    request: Request,
    file: Annotated[UploadFile, File()],
) -> BrandingResponse:
    settings = get_settings(request)
    store = get_store(request)

    if file.content_type not in {"image/png", "application/octet-stream", None}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logo must be a PNG image",
        )

    data = await file.read()
    if not data.startswith(PNG_SIGNATURE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logo must be a PNG image",
        )
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logo must be 512 KB or smaller",
        )

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    temp_path = settings.logo_path.with_suffix(".png.tmp")
    temp_path.write_bytes(data)
    os.replace(temp_path, settings.logo_path)
    store.set_setting(LOGO_UPDATED_AT_KEY, str(int(settings.logo_path.stat().st_mtime)))

    return branding_response(settings, store)


@router.delete(
    "/admin/branding/logo",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_pin)],
)
def delete_logo(request: Request) -> Response:
    settings = get_settings(request)
    store = get_store(request)
    if settings.logo_path.is_file():
        settings.logo_path.unlink()
    store.delete_setting(LOGO_UPDATED_AT_KEY)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
