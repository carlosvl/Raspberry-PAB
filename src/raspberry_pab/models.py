"""Typed data models for the offline schedule kiosk."""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, Field


class ParticipantBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    event_date: date
    start_time: time


class ParticipantCreate(ParticipantBase):
    pass


class ParticipantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    event_date: date | None = None
    start_time: time | None = None


class Participant(ParticipantBase):
    id: int


class ParticipantStatus(Participant):
    start_at: datetime
    countdown_seconds: int
    status: str


class ReminderRuleBase(BaseModel):
    offset_minutes: int = Field(ge=0)
    message_template: str = Field(min_length=1, max_length=240)
    repeat_every_minutes: int | None = Field(default=None, ge=1)
    enabled: bool = True
    sort_order: int = 0


class ReminderRuleCreate(ReminderRuleBase):
    pass


class ReminderRuleUpdate(BaseModel):
    offset_minutes: int | None = Field(default=None, ge=0)
    message_template: str | None = Field(default=None, min_length=1, max_length=240)
    repeat_every_minutes: int | None = Field(default=None, ge=1)
    enabled: bool | None = None
    sort_order: int | None = None


class ReminderRule(ReminderRuleBase):
    id: int


class ScheduleParticipantImport(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    start_time: time


class ScheduleImport(BaseModel):
    event_date: date
    participants: list[ScheduleParticipantImport] = Field(default_factory=list)
    reminder_rules: list[ReminderRuleCreate] = Field(default_factory=list)


class ScheduleExport(ScheduleImport):
    pass


class Alert(BaseModel):
    id: str
    participant_id: int
    rule_id: int
    name: str
    event_date: date
    start_time: time
    start_at: datetime
    fire_at: datetime
    message: str
    created_at: datetime
