"""Schedule and reminder-rule API routes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from raspberry_pab.config import Settings
from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import (
    Participant,
    ParticipantCreate,
    ParticipantStatus,
    ParticipantUpdate,
    ReminderRule,
    ReminderRuleCreate,
    ReminderRuleUpdate,
    ScheduleExport,
    ScheduleImport,
)
from raspberry_pab.kiosk_clock import effective_now
from raspberry_pab.reminders import participant_status, show_participant_on_board

router = APIRouter(prefix="/api", tags=["schedule"])


def get_store(request: Request) -> ScheduleStore:
    return cast(ScheduleStore, request.app.state.schedule_store)


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def require_admin_pin(
    request: Request,
    x_admin_pin: Annotated[str | None, Header(alias="X-Admin-Pin")] = None,
) -> None:
    settings = get_settings(request)
    if not x_admin_pin or x_admin_pin != settings.admin_pin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin PIN",
        )


@router.get("/admin/verify", dependencies=[Depends(require_admin_pin)])
def verify_admin_pin() -> dict[str, bool]:
    return {"authenticated": True}


@router.get("/participants", response_model=list[ParticipantStatus])
def list_participants(
    request: Request,
    date_filter: Annotated[date | None, Query(alias="date")] = None,
) -> list[ParticipantStatus]:
    store = get_store(request)
    now = effective_now(store)
    event_date = date_filter or now.date()
    results_map = store.get_participant_results_map(event_date)
    results: list[ParticipantStatus] = []
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
        if show_participant_on_board(status.countdown_seconds):
            results.append(status)
    return results


@router.post(
    "/participants",
    response_model=Participant,
    dependencies=[Depends(require_admin_pin)],
)
def create_participant(
    request: Request,
    participant: ParticipantCreate,
) -> Participant:
    return get_store(request).create_participant(participant)


@router.put(
    "/participants/{participant_id}",
    response_model=Participant,
    dependencies=[Depends(require_admin_pin)],
)
def update_participant(
    request: Request,
    participant_id: int,
    update: ParticipantUpdate,
) -> Participant:
    participant = get_store(request).update_participant(participant_id, update)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return participant


@router.delete(
    "/participants/{participant_id}",
    dependencies=[Depends(require_admin_pin)],
)
def delete_participant(request: Request, participant_id: int) -> dict[str, bool]:
    deleted = get_store(request).delete_participant(participant_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"deleted": True}


@router.get("/reminder-rules", response_model=list[ReminderRule])
def list_reminder_rules(request: Request) -> list[ReminderRule]:
    return get_store(request).list_rules()


@router.post(
    "/reminder-rules",
    response_model=ReminderRule,
    dependencies=[Depends(require_admin_pin)],
)
def create_reminder_rule(request: Request, rule: ReminderRuleCreate) -> ReminderRule:
    return get_store(request).create_rule(rule)


@router.put(
    "/reminder-rules/{rule_id}",
    response_model=ReminderRule,
    dependencies=[Depends(require_admin_pin)],
)
def update_reminder_rule(
    request: Request,
    rule_id: int,
    update: ReminderRuleUpdate,
) -> ReminderRule:
    rule = get_store(request).update_rule(rule_id, update)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return rule


@router.delete("/reminder-rules/{rule_id}", dependencies=[Depends(require_admin_pin)])
def delete_reminder_rule(request: Request, rule_id: int) -> dict[str, bool]:
    deleted = get_store(request).delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"deleted": True}


@router.post("/import", dependencies=[Depends(require_admin_pin)])
def import_schedule(request: Request, schedule: ScheduleImport) -> dict[str, bool]:
    get_store(request).import_schedule(schedule)
    return {"imported": True}


@router.get("/export", response_model=ScheduleExport)
def export_schedule(
    request: Request,
    date_filter: Annotated[date | None, Query(alias="date")] = None,
) -> ScheduleExport:
    return get_store(request).export_schedule(date_filter or date.today())
