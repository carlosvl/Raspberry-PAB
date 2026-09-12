"""Public TV board aggregator for the sideloaded Roku channel."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request

from raspberry_pab.branding import (
    effective_board_font_scale,
    effective_board_theme,
    effective_display_title,
    logo_url,
)
from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.kiosk_clock import effective_now, get_clock_state
from raspberry_pab.models import ParticipantStatus, TvBoardResponse
from raspberry_pab.network_info import lan_base_urls
from raspberry_pab.reminders import participant_status
from raspberry_pab.scheduler import AlertBroker

router = APIRouter(prefix="/api", tags=["tv-board"])


def _store(request: Request) -> ScheduleStore:
    return cast(ScheduleStore, request.app.state.schedule_store)


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _broker(request: Request) -> AlertBroker:
    return cast(AlertBroker, request.app.state.alert_broker)


@router.get("/tv-board", response_model=TvBoardResponse)
def tv_board(request: Request) -> TvBoardResponse:
    """Single poll payload for the Roku SceneGraph board."""
    store = _store(request)
    settings = _settings(request)
    clock = get_clock_state(store)
    now = effective_now(store)
    event_date = now.date()
    results_map = store.get_participant_results_map(event_date)
    participants: list[ParticipantStatus] = []
    for participant in store.list_participants(event_date):
        status = participant_status(participant, now)
        match = results_map.get(participant.id)
        if match is not None:
            status = status.model_copy(
                update={
                    "finish_place": match.place,
                    "finish_time": match.total_time,
                    "result_status": match.result_status,
                    "result_category": match.category_label,
                    "result_team": match.team_name,
                    "results_url": match.results_url,
                }
            )
        participants.append(status)

    logo = logo_url(settings, store)
    if logo and logo.startswith("/"):
        preferred = lan_base_urls(settings.port)
        if preferred:
            logo = f"{preferred[0]}{logo}"

    return TvBoardResponse(
        display_title=effective_display_title(settings, store),
        logo_url=logo,
        board_font_scale=effective_board_font_scale(store),
        board_theme=effective_board_theme(store),
        kiosk_now=str(clock["kiosk_now"]),
        display_date=str(clock["display_date"]),
        participants=participants,
        active_alert=_broker(request).active_alert,
        lan_urls=lan_base_urls(settings.port),
        poll_seconds=2,
    )
