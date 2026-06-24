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
    led_enabled: bool = False
    led_red: int = Field(default=255, ge=0, le=255)
    led_green: int = Field(default=200, ge=0, le=255)
    led_blue: int = Field(default=0, ge=0, le=255)
    led_flash_interval_ms: int = Field(default=500, ge=100, le=5000)
    led_flash_duration_seconds: int = Field(default=10, ge=1, le=120)
    led_chase_duration_seconds: int = Field(default=10, ge=0, le=120)


class ReminderRuleCreate(ReminderRuleBase):
    pass


class ReminderRuleUpdate(BaseModel):
    offset_minutes: int | None = Field(default=None, ge=0)
    message_template: str | None = Field(default=None, min_length=1, max_length=240)
    repeat_every_minutes: int | None = Field(default=None, ge=1)
    enabled: bool | None = None
    sort_order: int | None = None
    led_enabled: bool | None = None
    led_red: int | None = Field(default=None, ge=0, le=255)
    led_green: int | None = Field(default=None, ge=0, le=255)
    led_blue: int | None = Field(default=None, ge=0, le=255)
    led_flash_interval_ms: int | None = Field(default=None, ge=100, le=5000)
    led_flash_duration_seconds: int | None = Field(default=None, ge=1, le=120)
    led_chase_duration_seconds: int | None = Field(default=None, ge=0, le=120)


class ReminderRule(ReminderRuleBase):
    id: int


class LedStripTest(BaseModel):
    led_red: int = Field(ge=0, le=255)
    led_green: int = Field(ge=0, le=255)
    led_blue: int = Field(ge=0, le=255)
    led_flash_interval_ms: int = Field(default=500, ge=100, le=5000)
    led_flash_duration_seconds: int = Field(default=3, ge=1, le=120)
    led_chase_duration_seconds: int = Field(default=10, ge=0, le=120)


class ScheduleParticipantImport(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    start_time: time


class ScheduleImport(BaseModel):
    event_date: date
    participants: list[ScheduleParticipantImport] = Field(default_factory=list)
    reminder_rules: list[ReminderRuleCreate] = Field(default_factory=list)


class ScheduleExport(ScheduleImport):
    pass


class BrandingUpdate(BaseModel):
    display_title: str = Field(min_length=1, max_length=120)


class BrandingResponse(BaseModel):
    display_title: str
    has_logo: bool
    logo_url: str | None = None


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
