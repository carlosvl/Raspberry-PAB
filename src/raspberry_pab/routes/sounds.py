"""Admin routes for HDMI alert sound library."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Annotated, cast

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response

from raspberry_pab.config import Settings
from raspberry_pab.models import SoundFile, SoundTest
from raspberry_pab.routes.schedule import get_settings, get_store, require_admin_pin
from raspberry_pab.sound_controller import SoundController
from raspberry_pab.sound_library import (
    ALLOWED_SOUND_CONTENT_TYPES,
    MAX_SOUND_BYTES,
    extension_for_upload,
    stored_name_for,
)

router = APIRouter(prefix="/api", tags=["sounds"])

_NOT_FOUND = "Sound not found"


def get_sound_controller(request: Request) -> SoundController:
    return cast(SoundController, request.app.state.sound_controller)


def sound_file_path(settings: Settings, sound: SoundFile) -> Path:
    return settings.sounds_dir / sound.stored_name


@router.get(
    "/admin/sounds",
    response_model=list[SoundFile],
    dependencies=[Depends(require_admin_pin)],
)
def list_sounds(request: Request) -> list[SoundFile]:
    return get_store(request).list_sounds()


@router.post(
    "/admin/sounds",
    response_model=SoundFile,
    dependencies=[Depends(require_admin_pin)],
)
async def upload_sound(
    request: Request,
    file: Annotated[UploadFile, File()],
) -> SoundFile:
    settings = get_settings(request)
    store = get_store(request)

    content_type = (file.content_type or "").split(";")[0].strip().lower() or None
    if content_type and content_type not in ALLOWED_SOUND_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sound must be WAV, MP3, or OGG",
        )

    extension = extension_for_upload(file.filename, content_type)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sound must be WAV, MP3, or OGG",
        )

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sound file is empty",
        )
    if len(data) > MAX_SOUND_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sound must be 8 MB or smaller",
        )

    original_name = Path(file.filename or f"sound{extension}").name
    mime = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
    }[extension]

    placeholder = store.create_sound(
        original_name=original_name,
        stored_name="pending",
        content_type=mime,
        size_bytes=len(data),
    )
    final_name = stored_name_for(placeholder.id, extension)
    settings.sounds_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.sounds_dir / final_name
    temp_path = dest.with_suffix(dest.suffix + ".tmp")
    try:
        temp_path.write_bytes(data)
        os.replace(temp_path, dest)
    except Exception:
        store.delete_sound(placeholder.id)
        with contextlib.suppress(OSError):
            temp_path.unlink(missing_ok=True)
        raise

    updated = store.update_sound_stored_name(placeholder.id, final_name)
    if updated is None:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to finalize sound upload",
        )
    return updated


@router.delete(
    "/admin/sounds/{sound_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_pin)],
)
def delete_sound(request: Request, sound_id: int) -> Response:
    settings = get_settings(request)
    store = get_store(request)
    sound = store.get_sound(sound_id)
    if sound is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND,
        )

    in_use = store.count_rules_using_sound(sound_id)
    if in_use > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sound is used by {in_use} reminder rule(s)",
        )

    path = sound_file_path(settings, sound)
    store.delete_sound(sound_id)
    path.unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/admin/sounds/{sound_id}/test",
    dependencies=[Depends(require_admin_pin)],
)
async def test_sound(
    request: Request,
    sound_id: int,
    body: SoundTest,
) -> dict[str, bool]:
    settings = get_settings(request)
    if not settings.sound_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HDMI sound is disabled (PAB_SOUND_ENABLED)",
        )
    store = get_store(request)
    sound = store.get_sound(sound_id)
    if sound is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND,
        )
    path = sound_file_path(settings, sound)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sound file missing on disk",
        )

    controller = get_sound_controller(request)
    await controller.play_file(path, volume=body.volume, wait=False)
    return {"testing": True}


@router.get("/sounds/{sound_id}", dependencies=[Depends(require_admin_pin)])
def download_sound(request: Request, sound_id: int) -> FileResponse:
    settings = get_settings(request)
    store = get_store(request)
    sound = store.get_sound(sound_id)
    if sound is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND,
        )
    path = sound_file_path(settings, sound)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sound file missing on disk",
        )
    return FileResponse(
        path,
        media_type=sound.content_type,
        filename=sound.original_name,
    )
