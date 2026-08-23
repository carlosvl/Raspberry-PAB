"""Typed data models for the offline schedule kiosk."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field


MatrixEffect = Literal["solid", "rainbow", "pulse"]
MATRIX_EFFECTS: tuple[MatrixEffect, ...] = ("solid", "rainbow", "pulse")
MATRIX_EFFECT_MODE = {"solid": 0, "rainbow": 1, "pulse": 2}


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
    finish_place: int | None = None
    finish_time: str | None = None
    result_status: str | None = None
    result_category: str | None = None
    result_team: str | None = None
    results_url: str | None = None


class RaceEvent(BaseModel):
    id: int
    season_year: int
    race_number: str
    venue_label: str
    date_saturday: date
    date_sunday: date
    iyr_series_id: str
    iyr_base_url: str
    source_url: str
    scraped_at: datetime


class IyrRaceSession(BaseModel):
    id: int
    race_event_id: int
    iyr_eid: str
    category_label: str
    race_date: date
    results_url: str
    results_status: str
    scraped_at: datetime


class RaceResult(BaseModel):
    id: int
    participant_id: int
    iyr_session_id: int
    place: int
    bib: str | None = None
    team_name: str | None = None
    laps: int | None = None
    total_time: str | None = None
    total_distance: str | None = None
    raw_name: str
    match_confidence: float
    match_method: str
    result_status: str
    fetched_at: datetime


class ParticipantResultMatchRecord(BaseModel):
    participant_id: int
    participant_name: str
    event_date: date
    start_time: time
    place: int | None = None
    total_time: str | None = None
    team_name: str | None = None
    category_label: str | None = None
    venue_label: str | None = None
    match_method: str | None = None
    match_confidence: float | None = None
    result_status: str | None = None
    results_url: str | None = None
    match_state: str


class RaceResultsSyncSummary(BaseModel):
    event_date: date
    matched: int
    unmatched: int
    ambiguous: int
    sessions_synced: int


class ManualRaceResultLink(BaseModel):
    participant_id: int
    iyr_session_id: int
    place: int = Field(ge=1)
    bib: str | None = None
    team_name: str | None = None
    laps: int | None = Field(default=None, ge=0)
    total_time: str | None = None
    total_distance: str | None = None
    raw_name: str = Field(min_length=1, max_length=120)
    result_status: str = "official"


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
    matrix_effect: MatrixEffect = "solid"
    buzzer_enabled: bool = False
    buzzer_pitch_hz: int = Field(default=2500, ge=100, le=10000)
    buzzer_volume: int = Field(default=80, ge=0, le=100)
    buzzer_count: int = Field(default=3, ge=1, le=50)
    buzzer_beep_ms: int = Field(default=200, ge=10, le=5000)
    buzzer_gap_ms: int = Field(default=150, ge=0, le=5000)


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
    matrix_effect: MatrixEffect | None = None
    buzzer_enabled: bool | None = None
    buzzer_pitch_hz: int | None = Field(default=None, ge=100, le=10000)
    buzzer_volume: int | None = Field(default=None, ge=0, le=100)
    buzzer_count: int | None = Field(default=None, ge=1, le=50)
    buzzer_beep_ms: int | None = Field(default=None, ge=10, le=5000)
    buzzer_gap_ms: int | None = Field(default=None, ge=0, le=5000)


class ReminderRule(ReminderRuleBase):
    id: int


class BuzzerTest(BaseModel):
    buzzer_pitch_hz: int = Field(default=2500, ge=100, le=10000)
    buzzer_volume: int = Field(default=80, ge=0, le=100)
    buzzer_count: int = Field(default=3, ge=1, le=50)
    buzzer_beep_ms: int = Field(default=200, ge=10, le=5000)
    buzzer_gap_ms: int = Field(default=150, ge=0, le=5000)


class LedStripTest(BaseModel):
    led_red: int = Field(ge=0, le=255)
    led_green: int = Field(ge=0, le=255)
    led_blue: int = Field(ge=0, le=255)
    led_flash_interval_ms: int = Field(default=500, ge=100, le=5000)
    led_flash_duration_seconds: int = Field(default=3, ge=1, le=120)
    led_chase_duration_seconds: int = Field(default=10, ge=0, le=120)
    matrix_effect: MatrixEffect = "solid"
    message: str = Field(default="Matrix test", min_length=1, max_length=80)


class LedConfig(BaseModel):
    led_enabled: bool = False
    led_address: str = ""
    led_name: str = ""


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


class TouchConfigUpdate(BaseModel):
    tap_slop: int = Field(default=8, ge=1, le=40)
    drag_start: int = Field(default=12, ge=1, le=60)
    multi_tap_seconds: float = Field(default=0.45, ge=0.15, le=1.0)
    sensitivity: float = Field(default=0.5, ge=0.1, le=2.0)
    gamepad_enabled: bool = True
    gamepad_sensitivity: float = Field(default=8.0, ge=1.0, le=30.0)
    gamepad_deadzone: float = Field(default=0.15, ge=0.0, le=0.5)
    gamepad_edge_margin: int = Field(default=16, ge=4, le=64)
    gamepad_scroll_sensitivity: float = Field(default=0.35, ge=0.05, le=2.0)


class TouchConfigResponse(BaseModel):
    touch_map: str
    touch_lcd: str
    tap_slop: int
    drag_start: int
    multi_tap_seconds: float
    sensitivity: float
    gamepad_enabled: bool
    gamepad_sensitivity: float
    gamepad_deadzone: float
    gamepad_edge_margin: int
    gamepad_scroll_sensitivity: float
    gamepad_device: str | None = None


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


class TestScenarioRider(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    day: str = Field(pattern=r"^(saturday|sunday)$")


class TestScenarioDefinition(BaseModel):
    id: str
    label: str
    iyr_series_id: str
    saturday: date
    sunday: date
    first_start_time: str
    stagger_minutes: int = Field(ge=1, le=120)
    default_simulated_now: datetime
    roster: list[TestScenarioRider]


class TestScenarioSummary(BaseModel):
    id: str
    label: str
    saturday: date
    sunday: date
    roster_count: int


class TestScenarioRunResult(BaseModel):
    scenario_id: str
    label: str
    participants_seeded: int
    saturday: RaceResultsSyncSummary
    sunday: RaceResultsSyncSummary
    kiosk_date_suggested: date
    simulated_now: datetime


class KioskClockUpdate(BaseModel):
    simulated_now: datetime
    running: bool = True


class KioskClockAdvance(BaseModel):
    minutes: int = 1


class KioskClockState(BaseModel):
    simulated: bool
    running: bool
    anchor: str | None = None
    kiosk_now: str
    display_date: str


class WifiStatus(BaseModel):
    iface: str
    connection: str = ""
    ssid: str = ""
    ipv4: str = ""
    on_hotspot: bool = False
    state: str = ""
    hotspot_connection: str = "PAB-Hotspot"


class WifiSavedNetwork(BaseModel):
    name: str
    ssid: str
    uuid: str = ""
    security: str = ""


class WifiSavedNetworksResponse(BaseModel):
    networks: list[WifiSavedNetwork]


class WifiScanNetwork(BaseModel):
    ssid: str
    signal: int = 0
    security: str = ""
    in_use: bool = False
    secured: bool = False


class WifiScanResponse(BaseModel):
    networks: list[WifiScanNetwork]


class WifiConnectRequest(BaseModel):
    ssid: str = Field(min_length=1, max_length=32)
    password: str | None = Field(default=None, max_length=128)


class WifiConnectSavedRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class WifiConnectResponse(BaseModel):
    ok: bool = True
    ssid: str = ""
    connection: str = ""
    ipv4: str = ""
    name: str = ""
    message: str = ""


class WifiForgetResponse(BaseModel):
    ok: bool = True
    forgotten: str
