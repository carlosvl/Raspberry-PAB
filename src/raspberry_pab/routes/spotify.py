"""Admin routes for Spotify playback via the local go-librespot receiver."""

from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse

from raspberry_pab.config import Settings
from raspberry_pab.models import (
    SpotifyConfigUpdate,
    SpotifyPlaylist,
    SpotifyPlaylistsUpdate,
    SpotifyPlayRequest,
    SpotifyStatus,
    SpotifyVolume,
    SpotifyWebComplete,
    SpotifyWebItem,
    SpotifyWebLogin,
    SpotifyWebStatus,
)
from raspberry_pab.routes.schedule import get_store, require_admin_pin
from raspberry_pab.spotify_controller import SpotifyController
from raspberry_pab.spotify_library import (
    load_matrix_config,
    load_max_volume,
    load_playlists,
    normalize_spotify_uri,
    save_matrix_config,
    save_max_volume,
    save_playlists,
    steps_to_percent,
)
from raspberry_pab.spotify_web import (
    SpotifyNotConnectedError,
    SpotifyWebClient,
    SpotifyWebError,
)

router = APIRouter(prefix="/api", tags=["spotify"])

PlayerAction = Literal["pause", "resume", "next", "prev"]


def get_spotify_controller(request: Request) -> SpotifyController:
    return cast(SpotifyController, request.app.state.spotify_controller)


async def _status_response(request: Request) -> SpotifyStatus:
    controller = get_spotify_controller(request)
    store = get_store(request)
    playback = await controller.status()
    result = SpotifyStatus(
        enabled=controller.enabled(),
        online=playback is not None,
        max_volume=load_max_volume(store),
        playlists=load_playlists(store),
        matrix=load_matrix_config(store),
    )
    if playback is None:
        return result
    return result.model_copy(
        update={
            "playing": playback.playing,
            "paused": playback.paused,
            "stopped": playback.stopped,
            "volume": steps_to_percent(playback.volume, playback.volume_steps),
            "track_name": playback.track_name,
            "artist_names": list(playback.artist_names),
            "album_cover_url": playback.album_cover_url,
            "context_name": playback.context_name,
        }
    )


def _require_online(ok: bool, action: str) -> None:
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Spotify {action} failed (is Spotify enabled and online?)",
        )


@router.get(
    "/admin/spotify",
    response_model=SpotifyStatus,
    dependencies=[Depends(require_admin_pin)],
)
async def get_spotify(request: Request) -> SpotifyStatus:
    return await _status_response(request)


@router.put(
    "/admin/spotify",
    response_model=SpotifyStatus,
    dependencies=[Depends(require_admin_pin)],
)
async def put_spotify(request: Request, body: SpotifyConfigUpdate) -> SpotifyStatus:
    controller = get_spotify_controller(request)
    if body.enabled is not None:
        controller.set_enabled(body.enabled)
    if body.matrix is not None:
        save_matrix_config(get_store(request), body.matrix)
    if body.max_volume is not None:
        save_max_volume(get_store(request), body.max_volume)
        playback = await controller.status()
        if playback is not None:
            await controller.enforce_max_volume(playback)
    return await _status_response(request)


@router.post(
    "/admin/spotify/player/{action}",
    response_model=SpotifyStatus,
    dependencies=[Depends(require_admin_pin)],
)
async def player_action(request: Request, action: PlayerAction) -> SpotifyStatus:
    controller = get_spotify_controller(request)
    handlers = {
        "pause": controller.pause,
        "resume": controller.resume,
        "next": controller.next,
        "prev": controller.prev,
    }
    _require_online(await handlers[action](), action)
    return await _status_response(request)


@router.put(
    "/admin/spotify/volume",
    response_model=SpotifyStatus,
    dependencies=[Depends(require_admin_pin)],
)
async def put_volume(request: Request, body: SpotifyVolume) -> SpotifyStatus:
    controller = get_spotify_controller(request)
    _require_online(await controller.set_volume_percent(body.volume), "volume")
    return await _status_response(request)


@router.post(
    "/admin/spotify/play",
    response_model=SpotifyStatus,
    dependencies=[Depends(require_admin_pin)],
)
async def play_uri(request: Request, body: SpotifyPlayRequest) -> SpotifyStatus:
    try:
        uri = normalize_spotify_uri(body.uri)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    _require_online(await get_spotify_controller(request).play(uri), "play")
    return await _status_response(request)


@router.get(
    "/admin/spotify/playlists",
    response_model=list[SpotifyPlaylist],
    dependencies=[Depends(require_admin_pin)],
)
def get_playlists(request: Request) -> list[SpotifyPlaylist]:
    return load_playlists(get_store(request))


@router.put(
    "/admin/spotify/playlists",
    response_model=list[SpotifyPlaylist],
    dependencies=[Depends(require_admin_pin)],
)
def put_playlists(
    request: Request, body: SpotifyPlaylistsUpdate
) -> list[SpotifyPlaylist]:
    try:
        playlists = [
            SpotifyPlaylist(name=item.name.strip(), uri=normalize_spotify_uri(item.uri))
            for item in body.playlists
        ]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    save_playlists(get_store(request), playlists)
    return playlists


@router.post(
    "/admin/spotify/playlists/{index}/play",
    response_model=SpotifyStatus,
    dependencies=[Depends(require_admin_pin)],
)
async def play_playlist(request: Request, index: int) -> SpotifyStatus:
    playlists = load_playlists(get_store(request))
    if index < 0 or index >= len(playlists):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown playlist"
        )
    uri = playlists[index].uri
    _require_online(await get_spotify_controller(request).play(uri), "play")
    return await _status_response(request)


def get_spotify_web(request: Request) -> SpotifyWebClient:
    return cast(SpotifyWebClient, request.app.state.spotify_web)


def _web_error(exc: SpotifyWebError) -> HTTPException:
    code = (
        status.HTTP_409_CONFLICT
        if isinstance(exc, SpotifyNotConnectedError)
        else status.HTTP_502_BAD_GATEWAY
    )
    return HTTPException(status_code=code, detail=str(exc))


def _web_status(request: Request) -> SpotifyWebStatus:
    web = get_spotify_web(request)
    return SpotifyWebStatus(
        configured=web.configured,
        connected=web.connected,
        redirect_uri=cast(Settings, request.app.state.settings).spotify_redirect_uri,
    )


@router.get(
    "/admin/spotify/web",
    response_model=SpotifyWebStatus,
    dependencies=[Depends(require_admin_pin)],
)
def get_web_status(request: Request) -> SpotifyWebStatus:
    return _web_status(request)


@router.post(
    "/admin/spotify/web/login",
    response_model=SpotifyWebLogin,
    dependencies=[Depends(require_admin_pin)],
)
def start_web_login(request: Request) -> SpotifyWebLogin:
    try:
        url = get_spotify_web(request).start_login()
    except SpotifyWebError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return SpotifyWebLogin(authorize_url=url)


@router.post(
    "/admin/spotify/web/complete",
    response_model=SpotifyWebStatus,
    dependencies=[Depends(require_admin_pin)],
)
async def complete_web_login(
    request: Request, body: SpotifyWebComplete
) -> SpotifyWebStatus:
    try:
        await get_spotify_web(request).finish_login_from_url(body.redirect_url)
    except SpotifyWebError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return _web_status(request)


@router.get("/spotify/callback", response_class=HTMLResponse)
async def web_login_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
) -> HTMLResponse:
    """Spotify redirects here when the login is done on the Pi itself.

    No admin PIN: the one-time state from the PIN-gated login start
    protects it.
    """
    try:
        await get_spotify_web(request).finish_login(code=code, state=state, error=error)
    except SpotifyWebError as exc:
        return HTMLResponse(_callback_page(f"Spotify not connected: {exc}"), 400)
    return HTMLResponse(_callback_page("Spotify connected. You can close this tab."))


def _callback_page(message: str) -> str:
    safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!doctype html><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        "<title>Spotify</title>"
        '<body style="font-family:system-ui;padding:2rem;background:#0b1220;'
        f'color:#e5e7eb"><h1>{safe}</h1><p><a style="color:#60a5fa" '
        'href="/admin">Back to Admin</a></p></body>'
    )


@router.delete(
    "/admin/spotify/web",
    response_model=SpotifyWebStatus,
    dependencies=[Depends(require_admin_pin)],
)
def disconnect_web(request: Request) -> SpotifyWebStatus:
    get_spotify_web(request).disconnect()
    return _web_status(request)


@router.get(
    "/admin/spotify/web/playlists",
    response_model=list[SpotifyWebItem],
    dependencies=[Depends(require_admin_pin)],
)
async def web_playlists(request: Request) -> list[SpotifyWebItem]:
    try:
        return await get_spotify_web(request).my_playlists()
    except SpotifyWebError as exc:
        raise _web_error(exc) from exc


@router.get(
    "/admin/spotify/web/search",
    response_model=list[SpotifyWebItem],
    dependencies=[Depends(require_admin_pin)],
)
async def web_search(
    request: Request, q: str = Query(min_length=1, max_length=100)
) -> list[SpotifyWebItem]:
    try:
        return await get_spotify_web(request).search(q)
    except SpotifyWebError as exc:
        raise _web_error(exc) from exc
