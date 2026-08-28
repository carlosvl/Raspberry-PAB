"""Schedule and reminder-rule API routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated, cast

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)

from raspberry_pab.arduino_serial import effective_matrix_port
from raspberry_pab.config import Settings
from raspberry_pab.csv_import import parse_schedule_csv
from raspberry_pab.db import ScheduleStore
from raspberry_pab.kiosk_clock import effective_now
from raspberry_pab.models import (
    Participant,
    ParticipantCreate,
    ParticipantStatus,
    ParticipantUpdate,
    ReminderRule,
    ReminderRuleCreate,
    ReminderRuleUpdate,
    ScheduleCsvImportResult,
    ScheduleExport,
    ScheduleImport,
)
from raspberry_pab.reminders import participant_status

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


@router.get("/admin/hardware-status", dependencies=[Depends(require_admin_pin)])
def hardware_status(request: Request) -> dict[str, object]:
    settings = get_settings(request)
    return {
        "buzzer_enabled": settings.buzzer_enabled,
        "buzzer_port": settings.buzzer_port or "",
        "led_enabled": settings.led_enabled,
        "led_address": settings.led_address or "",
        "matrix_enabled": settings.matrix_enabled,
        "matrix_port": effective_matrix_port(settings) or "",
        "matrix_brightness": settings.matrix_brightness,
        "sound_enabled": settings.sound_enabled,
        "sound_sink": settings.sound_sink or "",
    }


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


@router.post(
    "/import/csv",
    response_model=ScheduleCsvImportResult,
    dependencies=[Depends(require_admin_pin)],
)
async def import_schedule_csv(
    request: Request,
    file: Annotated[UploadFile, File()],
    event_date: Annotated[date | None, Form()] = None,
) -> ScheduleCsvImportResult:
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must be UTF-8 text",
        ) from exc
    try:
        schedule = parse_schedule_csv(text, event_date=event_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    get_store(request).import_schedule(schedule)
    columns = sorted(
        {
            key
            for participant in schedule.participants
            for key, value in (
                ("name", participant.name),
                ("race", participant.race),
                ("call_up", participant.call_up),
                ("start_time", participant.start_time),
            )
            if value not in (None, "")
        }
        | {"name", "start_time"}
    )
    return ScheduleCsvImportResult(
        imported=True,
        event_date=schedule.event_date,
        participant_count=len(schedule.participants),
        columns=columns,
    )


@router.get("/export", response_model=ScheduleExport)
def export_schedule(
    request: Request,
    date_filter: Annotated[date | None, Query(alias="date")] = None,
) -> ScheduleExport:
    return get_store(request).export_schedule(date_filter or date.today())
