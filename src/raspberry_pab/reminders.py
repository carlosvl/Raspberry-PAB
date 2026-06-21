"""Reminder timing and formatting logic."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from raspberry_pab.models import Alert, Participant, ParticipantStatus, ReminderRule


def participant_start_at(event_date: date, start_time: time) -> datetime:
    return datetime.combine(event_date, start_time)


def render_message(template: str, participant: Participant) -> str:
    return template.replace("{name}", participant.name)


def compute_fire_times(start_at: datetime, rule: ReminderRule) -> list[datetime]:
    first_fire = start_at - timedelta(minutes=rule.offset_minutes)
    if rule.repeat_every_minutes is None:
        return [first_fire]

    interval = timedelta(minutes=rule.repeat_every_minutes)
    fire_times: list[datetime] = []
    current = first_fire
    while current < start_at or (rule.offset_minutes == 0 and current == start_at):
        fire_times.append(current)
        current += interval
    return fire_times


def is_due(fire_at: datetime, now: datetime, *, window_seconds: int = 2) -> bool:
    elapsed = (now - fire_at).total_seconds()
    return 0 <= elapsed < window_seconds


def participant_status(participant: Participant, now: datetime) -> ParticipantStatus:
    start_at = participant_start_at(participant.event_date, participant.start_time)
    countdown_seconds = int((start_at - now).total_seconds())
    if countdown_seconds > 0:
        status = "upcoming"
    elif countdown_seconds > -60:
        status = "live"
    else:
        status = "past"
    return ParticipantStatus(
        id=participant.id,
        name=participant.name,
        event_date=participant.event_date,
        start_time=participant.start_time,
        start_at=start_at,
        countdown_seconds=countdown_seconds,
        status=status,
    )


def build_due_alerts(
    participants: list[Participant],
    rules: list[ReminderRule],
    now: datetime,
) -> list[Alert]:
    alerts: list[Alert] = []
    created_at = now
    for participant in participants:
        start_at = participant_start_at(participant.event_date, participant.start_time)
        for rule in rules:
            for fire_at in compute_fire_times(start_at, rule):
                if not is_due(fire_at, now):
                    continue
                alert_id = f"{participant.id}:{rule.id}:{fire_at.isoformat()}"
                alerts.append(
                    Alert(
                        id=alert_id,
                        participant_id=participant.id,
                        rule_id=rule.id,
                        name=participant.name,
                        event_date=participant.event_date,
                        start_time=participant.start_time,
                        start_at=start_at,
                        fire_at=fire_at,
                        message=render_message(rule.message_template, participant),
                        created_at=created_at,
                    )
                )
    return alerts
