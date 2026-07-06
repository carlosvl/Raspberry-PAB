"""SQLite storage for schedules, reminder rules, and fired alerts."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from raspberry_pab.models import (
    Alert,
    IyrRaceSession,
    ManualRaceResultLink,
    Participant,
    ParticipantCreate,
    ParticipantResultMatchRecord,
    ParticipantUpdate,
    RaceEvent,
    RaceResult,
    ReminderRule,
    ReminderRuleCreate,
    ReminderRuleUpdate,
    ScheduleExport,
    ScheduleImport,
    ScheduleParticipantImport,
)

DEFAULT_RULES = (
    ReminderRuleCreate(
        offset_minutes=30,
        message_template="Warm Up {name}",
        sort_order=0,
    ),
    ReminderRuleCreate(
        offset_minutes=15,
        message_template="Go to Start Line",
        repeat_every_minutes=5,
        sort_order=1,
    ),
)


class ScheduleStore:
    """Small SQLite repository used by API routes and the reminder scheduler."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    start_time TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_participants_event_date
                    ON participants (event_date, start_time);

                CREATE TABLE IF NOT EXISTS reminder_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    offset_minutes INTEGER NOT NULL CHECK (offset_minutes >= 0),
                    message_template TEXT NOT NULL,
                    repeat_every_minutes INTEGER CHECK (
                        repeat_every_minutes IS NULL
                        OR repeat_every_minutes > 0
                    ),
                    enabled INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS fired_alerts (
                    participant_id INTEGER NOT NULL,
                    rule_id INTEGER NOT NULL,
                    fire_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (participant_id, rule_id, fire_at),
                    FOREIGN KEY (participant_id)
                        REFERENCES participants (id) ON DELETE CASCADE,
                    FOREIGN KEY (rule_id)
                        REFERENCES reminder_rules (id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS race_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    season_year INTEGER NOT NULL,
                    race_number TEXT NOT NULL,
                    venue_label TEXT NOT NULL,
                    date_saturday TEXT NOT NULL,
                    date_sunday TEXT NOT NULL,
                    iyr_series_id TEXT NOT NULL UNIQUE,
                    iyr_base_url TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    scraped_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_race_events_dates
                    ON race_events (date_saturday, date_sunday);

                CREATE TABLE IF NOT EXISTS iyr_race_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    race_event_id INTEGER NOT NULL,
                    iyr_eid TEXT NOT NULL,
                    category_label TEXT NOT NULL,
                    race_date TEXT NOT NULL,
                    results_url TEXT NOT NULL,
                    results_status TEXT NOT NULL,
                    scraped_at TEXT NOT NULL,
                    UNIQUE (race_event_id, iyr_eid),
                    FOREIGN KEY (race_event_id)
                        REFERENCES race_events (id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_iyr_sessions_date
                    ON iyr_race_sessions (race_date);

                CREATE TABLE IF NOT EXISTS race_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    participant_id INTEGER NOT NULL UNIQUE,
                    iyr_session_id INTEGER NOT NULL,
                    place INTEGER NOT NULL,
                    bib TEXT,
                    team_name TEXT,
                    laps INTEGER,
                    total_time TEXT,
                    total_distance TEXT,
                    raw_name TEXT NOT NULL,
                    match_confidence REAL NOT NULL,
                    match_method TEXT NOT NULL,
                    result_status TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    FOREIGN KEY (participant_id)
                        REFERENCES participants (id) ON DELETE CASCADE,
                    FOREIGN KEY (iyr_session_id)
                        REFERENCES iyr_race_sessions (id) ON DELETE CASCADE
                );
                """
            )
            self._migrate_rule_led_columns(conn)
            self._migrate_rule_buzzer_columns(conn)
            count = conn.execute("SELECT COUNT(*) FROM reminder_rules").fetchone()[0]
            if count == 0:
                self._create_rules(conn, DEFAULT_RULES)
            conn.commit()

    def list_participants(self, event_date: date | None = None) -> list[Participant]:
        query = "SELECT id, name, event_date, start_time FROM participants"
        params: tuple[str, ...] = ()
        if event_date is not None:
            query += " WHERE event_date = ?"
            params = (event_date.isoformat(),)
        query += " ORDER BY event_date, start_time, name"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._participant_from_row(row) for row in rows]

    def get_participant(self, participant_id: int) -> Participant | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, event_date, start_time
                FROM participants
                WHERE id = ?
                """,
                (participant_id,),
            ).fetchone()
        return self._participant_from_row(row) if row is not None else None

    def create_participant(self, participant: ParticipantCreate) -> Participant:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO participants (name, event_date, start_time)
                VALUES (?, ?, ?)
                """,
                (
                    participant.name.strip(),
                    participant.event_date.isoformat(),
                    participant.start_time.isoformat(timespec="minutes"),
                ),
            )
            conn.commit()
            if cursor.lastrowid is None:
                raise RuntimeError("Failed to create participant")
            participant_id = cursor.lastrowid
        created = self.get_participant(participant_id)
        if created is None:
            raise RuntimeError("Failed to load created participant")
        return created

    def update_participant(
        self, participant_id: int, update: ParticipantUpdate
    ) -> Participant | None:
        existing = self.get_participant(participant_id)
        if existing is None:
            return None
        merged = ParticipantCreate(
            name=(update.name if update.name is not None else existing.name),
            event_date=(
                update.event_date
                if update.event_date is not None
                else existing.event_date
            ),
            start_time=(
                update.start_time
                if update.start_time is not None
                else existing.start_time
            ),
        )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE participants
                SET name = ?, event_date = ?, start_time = ?
                WHERE id = ?
                """,
                (
                    merged.name.strip(),
                    merged.event_date.isoformat(),
                    merged.start_time.isoformat(timespec="minutes"),
                    participant_id,
                ),
            )
            conn.commit()
        return self.get_participant(participant_id)

    def delete_participant(self, participant_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM participants WHERE id = ?", (participant_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_rules(self, *, enabled_only: bool = False) -> list[ReminderRule]:
        query = """
            SELECT id, offset_minutes, message_template, repeat_every_minutes,
                   enabled, sort_order, led_enabled, led_red, led_green, led_blue,
                   led_flash_interval_ms, led_flash_duration_seconds,
                   led_chase_duration_seconds,
                   buzzer_enabled, buzzer_pitch_hz, buzzer_volume,
                   buzzer_count, buzzer_beep_ms, buzzer_gap_ms
            FROM reminder_rules
        """
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY sort_order, offset_minutes DESC, id"
        with self._connect() as conn:
            rows = conn.execute(query).fetchall()
        return [self._rule_from_row(row) for row in rows]

    def get_rule(self, rule_id: int) -> ReminderRule | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, offset_minutes, message_template, repeat_every_minutes,
                       enabled, sort_order, led_enabled, led_red, led_green, led_blue,
                       led_flash_interval_ms, led_flash_duration_seconds,
                   led_chase_duration_seconds,
                   buzzer_enabled, buzzer_pitch_hz, buzzer_volume,
                   buzzer_count, buzzer_beep_ms, buzzer_gap_ms
                FROM reminder_rules
                WHERE id = ?
                """,
                (rule_id,),
            ).fetchone()
        return self._rule_from_row(row) if row is not None else None

    def create_rule(self, rule: ReminderRuleCreate) -> ReminderRule:
        with self._connect() as conn:
            cursor = self._create_rules(conn, (rule,))
            conn.commit()
            if cursor.lastrowid is None:
                raise RuntimeError("Failed to create reminder rule")
            rule_id = cursor.lastrowid
        created = self.get_rule(rule_id)
        if created is None:
            raise RuntimeError("Failed to load created reminder rule")
        return created

    def update_rule(
        self, rule_id: int, update: ReminderRuleUpdate
    ) -> ReminderRule | None:
        existing = self.get_rule(rule_id)
        if existing is None:
            return None
        merged = ReminderRuleCreate(
            offset_minutes=(
                update.offset_minutes
                if update.offset_minutes is not None
                else existing.offset_minutes
            ),
            message_template=(
                update.message_template
                if update.message_template is not None
                else existing.message_template
            ),
            repeat_every_minutes=(
                update.repeat_every_minutes
                if update.repeat_every_minutes is not None
                else existing.repeat_every_minutes
            ),
            enabled=update.enabled if update.enabled is not None else existing.enabled,
            sort_order=(
                update.sort_order
                if update.sort_order is not None
                else existing.sort_order
            ),
            led_enabled=(
                update.led_enabled
                if update.led_enabled is not None
                else existing.led_enabled
            ),
            led_red=update.led_red if update.led_red is not None else existing.led_red,
            led_green=(
                update.led_green if update.led_green is not None else existing.led_green
            ),
            led_blue=(
                update.led_blue if update.led_blue is not None else existing.led_blue
            ),
            led_flash_interval_ms=(
                update.led_flash_interval_ms
                if update.led_flash_interval_ms is not None
                else existing.led_flash_interval_ms
            ),
            led_flash_duration_seconds=(
                update.led_flash_duration_seconds
                if update.led_flash_duration_seconds is not None
                else existing.led_flash_duration_seconds
            ),
            led_chase_duration_seconds=(
                update.led_chase_duration_seconds
                if update.led_chase_duration_seconds is not None
                else existing.led_chase_duration_seconds
            ),
            buzzer_enabled=(
                update.buzzer_enabled
                if update.buzzer_enabled is not None
                else existing.buzzer_enabled
            ),
            buzzer_pitch_hz=(
                update.buzzer_pitch_hz
                if update.buzzer_pitch_hz is not None
                else existing.buzzer_pitch_hz
            ),
            buzzer_volume=(
                update.buzzer_volume
                if update.buzzer_volume is not None
                else existing.buzzer_volume
            ),
            buzzer_count=(
                update.buzzer_count
                if update.buzzer_count is not None
                else existing.buzzer_count
            ),
            buzzer_beep_ms=(
                update.buzzer_beep_ms
                if update.buzzer_beep_ms is not None
                else existing.buzzer_beep_ms
            ),
            buzzer_gap_ms=(
                update.buzzer_gap_ms
                if update.buzzer_gap_ms is not None
                else existing.buzzer_gap_ms
            ),
        )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE reminder_rules
                SET offset_minutes = ?, message_template = ?,
                    repeat_every_minutes = ?, enabled = ?, sort_order = ?,
                    led_enabled = ?, led_red = ?, led_green = ?, led_blue = ?,
                    led_flash_interval_ms = ?, led_flash_duration_seconds = ?,
                    led_chase_duration_seconds = ?,
                    buzzer_enabled = ?, buzzer_pitch_hz = ?, buzzer_volume = ?,
                    buzzer_count = ?, buzzer_beep_ms = ?, buzzer_gap_ms = ?
                WHERE id = ?
                """,
                (
                    merged.offset_minutes,
                    merged.message_template.strip(),
                    merged.repeat_every_minutes,
                    int(merged.enabled),
                    merged.sort_order,
                    int(merged.led_enabled),
                    merged.led_red,
                    merged.led_green,
                    merged.led_blue,
                    merged.led_flash_interval_ms,
                    merged.led_flash_duration_seconds,
                    merged.led_chase_duration_seconds,
                    int(merged.buzzer_enabled),
                    merged.buzzer_pitch_hz,
                    merged.buzzer_volume,
                    merged.buzzer_count,
                    merged.buzzer_beep_ms,
                    merged.buzzer_gap_ms,
                    rule_id,
                ),
            )
            conn.commit()
        return self.get_rule(rule_id)

    def delete_rule(self, rule_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM reminder_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return cursor.rowcount > 0

    def import_schedule(self, schedule: ScheduleImport) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM participants WHERE event_date = ?",
                (schedule.event_date.isoformat(),),
            )
            conn.executemany(
                """
                INSERT INTO participants (name, event_date, start_time)
                VALUES (?, ?, ?)
                """,
                [
                    (
                        participant.name.strip(),
                        schedule.event_date.isoformat(),
                        participant.start_time.isoformat(timespec="minutes"),
                    )
                    for participant in schedule.participants
                ],
            )
            if schedule.reminder_rules:
                conn.execute("DELETE FROM reminder_rules")
                self._create_rules(conn, schedule.reminder_rules)
            conn.commit()

    def export_schedule(self, event_date: date) -> ScheduleExport:
        participants = [
            ScheduleParticipantImport(name=item.name, start_time=item.start_time)
            for item in self.list_participants(event_date)
        ]
        rules = [
            ReminderRuleCreate(
                offset_minutes=rule.offset_minutes,
                message_template=rule.message_template,
                repeat_every_minutes=rule.repeat_every_minutes,
                enabled=rule.enabled,
                sort_order=rule.sort_order,
                led_enabled=rule.led_enabled,
                led_red=rule.led_red,
                led_green=rule.led_green,
                led_blue=rule.led_blue,
                led_flash_interval_ms=rule.led_flash_interval_ms,
                led_flash_duration_seconds=rule.led_flash_duration_seconds,
                led_chase_duration_seconds=rule.led_chase_duration_seconds,
                buzzer_enabled=rule.buzzer_enabled,
                buzzer_pitch_hz=rule.buzzer_pitch_hz,
                buzzer_volume=rule.buzzer_volume,
                buzzer_count=rule.buzzer_count,
                buzzer_beep_ms=rule.buzzer_beep_ms,
                buzzer_gap_ms=rule.buzzer_gap_ms,
            )
            for rule in self.list_rules()
        ]
        return ScheduleExport(
            event_date=event_date,
            participants=participants,
            reminder_rules=rules,
        )

    def get_setting(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (key,),
            ).fetchone()
        return str(row["value"]) if row is not None else None

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            conn.commit()

    def delete_setting(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
            conn.commit()

    def record_fired_alert(self, alert: Alert) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO fired_alerts
                    (participant_id, rule_id, fire_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    alert.participant_id,
                    alert.rule_id,
                    alert.fire_at.isoformat(),
                    alert.created_at.isoformat(),
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_participants_for_date(self, event_date: date) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM participants WHERE event_date = ?",
                (event_date.isoformat(),),
            )
            conn.commit()
            return cursor.rowcount

    def delete_race_results_for_dates(self, dates: list[date]) -> int:
        """Delete race results linked to participants on the given dates.

        Note: race_results has ON DELETE CASCADE from participants, so
        deleting participants already cascades.  This method is for
        explicitly removing results while keeping participants.
        """
        if not dates:
            return 0
        placeholders = ",".join("?" for _ in dates)
        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                DELETE FROM race_results
                WHERE participant_id IN (
                    SELECT id FROM participants WHERE event_date IN ({placeholders})
                )
                """,
                [d.isoformat() for d in dates],
            )
            conn.commit()
            return cursor.rowcount

    def upsert_race_events(self, events: Iterable[object]) -> list[RaceEvent]:
        now = datetime.now().isoformat()
        stored: list[RaceEvent] = []
        with self._connect() as conn:
            for event in events:
                conn.execute(
                    """
                    INSERT INTO race_events (
                        season_year, race_number, venue_label,
                        date_saturday, date_sunday, iyr_series_id,
                        iyr_base_url, source_url, scraped_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(iyr_series_id) DO UPDATE SET
                        season_year = excluded.season_year,
                        race_number = excluded.race_number,
                        venue_label = excluded.venue_label,
                        date_saturday = excluded.date_saturday,
                        date_sunday = excluded.date_sunday,
                        iyr_base_url = excluded.iyr_base_url,
                        source_url = excluded.source_url,
                        scraped_at = excluded.scraped_at
                    """,
                    (
                        event.season_year,
                        event.race_number,
                        event.venue_label,
                        event.date_saturday.isoformat(),
                        event.date_sunday.isoformat(),
                        event.iyr_series_id,
                        event.iyr_base_url,
                        event.source_url,
                        now,
                    ),
                )
            conn.commit()
            rows = conn.execute(
                "SELECT * FROM race_events ORDER BY season_year DESC, date_saturday DESC"
            ).fetchall()
        return [self._race_event_from_row(row) for row in rows]

    def list_race_events(self) -> list[RaceEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM race_events ORDER BY season_year DESC, date_saturday DESC"
            ).fetchall()
        return [self._race_event_from_row(row) for row in rows]

    def get_race_event_by_series_id(self, series_id: str) -> RaceEvent | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM race_events WHERE iyr_series_id = ?",
                (series_id,),
            ).fetchone()
        return self._race_event_from_row(row) if row is not None else None

    def upsert_iyr_session(
        self,
        *,
        race_event_id: int,
        iyr_eid: str,
        category_label: str,
        race_date: date,
        results_url: str,
        results_status: str,
    ) -> IyrRaceSession:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO iyr_race_sessions (
                    race_event_id, iyr_eid, category_label, race_date,
                    results_url, results_status, scraped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(race_event_id, iyr_eid) DO UPDATE SET
                    category_label = excluded.category_label,
                    race_date = excluded.race_date,
                    results_url = excluded.results_url,
                    results_status = excluded.results_status,
                    scraped_at = excluded.scraped_at
                """,
                (
                    race_event_id,
                    iyr_eid,
                    category_label,
                    race_date.isoformat(),
                    results_url,
                    results_status,
                    now,
                ),
            )
            row = conn.execute(
                """
                SELECT * FROM iyr_race_sessions
                WHERE race_event_id = ? AND iyr_eid = ?
                """,
                (race_event_id, iyr_eid),
            ).fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to upsert IYR session")
        return self._iyr_session_from_row(row)

    def list_iyr_sessions_for_event(
        self,
        race_event_id: int,
        race_date: date | None = None,
    ) -> list[IyrRaceSession]:
        query = "SELECT * FROM iyr_race_sessions WHERE race_event_id = ?"
        params: list[object] = [race_event_id]
        if race_date is not None:
            query += " AND race_date = ?"
            params.append(race_date.isoformat())
        query += " ORDER BY category_label"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._iyr_session_from_row(row) for row in rows]

    def upsert_race_result(
        self,
        *,
        participant_id: int,
        iyr_session_id: int,
        place: int,
        bib: str | None,
        team_name: str | None,
        laps: int | None,
        total_time: str | None,
        total_distance: str | None,
        raw_name: str,
        match_confidence: float,
        match_method: str,
        result_status: str,
    ) -> RaceResult:
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO race_results (
                    participant_id, iyr_session_id, place, bib, team_name,
                    laps, total_time, total_distance, raw_name,
                    match_confidence, match_method, result_status, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(participant_id) DO UPDATE SET
                    iyr_session_id = excluded.iyr_session_id,
                    place = excluded.place,
                    bib = excluded.bib,
                    team_name = excluded.team_name,
                    laps = excluded.laps,
                    total_time = excluded.total_time,
                    total_distance = excluded.total_distance,
                    raw_name = excluded.raw_name,
                    match_confidence = excluded.match_confidence,
                    match_method = excluded.match_method,
                    result_status = excluded.result_status,
                    fetched_at = excluded.fetched_at
                """,
                (
                    participant_id,
                    iyr_session_id,
                    place,
                    bib,
                    team_name,
                    laps,
                    total_time,
                    total_distance,
                    raw_name,
                    match_confidence,
                    match_method,
                    result_status,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM race_results WHERE participant_id = ?",
                (participant_id,),
            ).fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to upsert race result")
        return self._race_result_from_row(row)

    def get_race_result_for_participant(self, participant_id: int) -> RaceResult | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM race_results WHERE participant_id = ?",
                (participant_id,),
            ).fetchone()
        return self._race_result_from_row(row) if row is not None else None

    def link_race_result_manual(self, link: ManualRaceResultLink) -> RaceResult:
        return self.upsert_race_result(
            participant_id=link.participant_id,
            iyr_session_id=link.iyr_session_id,
            place=link.place,
            bib=link.bib,
            team_name=link.team_name,
            laps=link.laps,
            total_time=link.total_time,
            total_distance=link.total_distance,
            raw_name=link.raw_name,
            match_confidence=1.0,
            match_method="manual",
            result_status=link.result_status,
        )

    def list_participant_result_matches(
        self,
        event_date: date,
    ) -> list[ParticipantResultMatchRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    p.id AS participant_id,
                    p.name AS participant_name,
                    p.event_date,
                    p.start_time,
                    rr.place,
                    rr.total_time,
                    rr.team_name,
                    rr.match_method,
                    rr.match_confidence,
                    rr.result_status,
                    s.category_label,
                    s.results_url,
                    e.venue_label
                FROM participants p
                LEFT JOIN race_results rr ON rr.participant_id = p.id
                LEFT JOIN iyr_race_sessions s ON s.id = rr.iyr_session_id
                LEFT JOIN race_events e ON e.id = s.race_event_id
                WHERE p.event_date = ?
                ORDER BY p.start_time, p.name
                """,
                (event_date.isoformat(),),
            ).fetchall()
        results: list[ParticipantResultMatchRecord] = []
        for row in rows:
            if row["place"] is None:
                state = "unmatched"
            else:
                state = "matched"
            results.append(
                ParticipantResultMatchRecord(
                    participant_id=int(row["participant_id"]),
                    participant_name=str(row["participant_name"]),
                    event_date=date.fromisoformat(str(row["event_date"])),
                    start_time=datetime.strptime(str(row["start_time"]), "%H:%M").time(),
                    place=int(row["place"]) if row["place"] is not None else None,
                    total_time=row["total_time"],
                    team_name=row["team_name"],
                    category_label=row["category_label"],
                    venue_label=row["venue_label"],
                    match_method=row["match_method"],
                    match_confidence=row["match_confidence"],
                    result_status=row["result_status"],
                    results_url=row["results_url"],
                    match_state=state,
                )
            )
        return results

    def get_participant_results_map(
        self,
        event_date: date,
    ) -> dict[int, ParticipantResultMatchRecord]:
        return {
            item.participant_id: item
            for item in self.list_participant_result_matches(event_date)
            if item.match_state == "matched"
        }

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _migrate_rule_led_columns(conn: sqlite3.Connection) -> None:
        columns = (
            ("led_enabled", "INTEGER NOT NULL DEFAULT 0"),
            ("led_red", "INTEGER NOT NULL DEFAULT 255"),
            ("led_green", "INTEGER NOT NULL DEFAULT 200"),
            ("led_blue", "INTEGER NOT NULL DEFAULT 0"),
            ("led_flash_interval_ms", "INTEGER NOT NULL DEFAULT 500"),
            ("led_flash_duration_seconds", "INTEGER NOT NULL DEFAULT 10"),
            ("led_chase_duration_seconds", "INTEGER NOT NULL DEFAULT 10"),
        )
        for name, spec in columns:
            try:
                conn.execute(f"ALTER TABLE reminder_rules ADD COLUMN {name} {spec}")
            except sqlite3.OperationalError:
                continue

    @staticmethod
    def _migrate_rule_buzzer_columns(conn: sqlite3.Connection) -> None:
        columns = (
            ("buzzer_enabled", "INTEGER NOT NULL DEFAULT 0"),
            ("buzzer_pitch_hz", "INTEGER NOT NULL DEFAULT 2500"),
            ("buzzer_volume", "INTEGER NOT NULL DEFAULT 80"),
            ("buzzer_count", "INTEGER NOT NULL DEFAULT 3"),
            ("buzzer_beep_ms", "INTEGER NOT NULL DEFAULT 200"),
            ("buzzer_gap_ms", "INTEGER NOT NULL DEFAULT 150"),
        )
        for name, spec in columns:
            try:
                conn.execute(f"ALTER TABLE reminder_rules ADD COLUMN {name} {spec}")
            except sqlite3.OperationalError:
                continue

    @staticmethod
    def _create_rules(
        conn: sqlite3.Connection, rules: Iterable[ReminderRuleCreate]
    ) -> sqlite3.Cursor:
        cursor = conn.cursor()
        for rule in rules:
            cursor.execute(
                """
                INSERT INTO reminder_rules
                    (offset_minutes, message_template, repeat_every_minutes,
                     enabled, sort_order, led_enabled, led_red, led_green, led_blue,
                     led_flash_interval_ms, led_flash_duration_seconds,
                     led_chase_duration_seconds,
                     buzzer_enabled, buzzer_pitch_hz, buzzer_volume,
                     buzzer_count, buzzer_beep_ms, buzzer_gap_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.offset_minutes,
                    rule.message_template.strip(),
                    rule.repeat_every_minutes,
                    int(rule.enabled),
                    rule.sort_order,
                    int(rule.led_enabled),
                    rule.led_red,
                    rule.led_green,
                    rule.led_blue,
                    rule.led_flash_interval_ms,
                    rule.led_flash_duration_seconds,
                    rule.led_chase_duration_seconds,
                    int(rule.buzzer_enabled),
                    rule.buzzer_pitch_hz,
                    rule.buzzer_volume,
                    rule.buzzer_count,
                    rule.buzzer_beep_ms,
                    rule.buzzer_gap_ms,
                ),
            )
        return cursor

    @staticmethod
    def _participant_from_row(row: sqlite3.Row) -> Participant:
        return Participant(
            id=int(row["id"]),
            name=str(row["name"]),
            event_date=date.fromisoformat(str(row["event_date"])),
            start_time=datetime.strptime(str(row["start_time"]), "%H:%M").time(),
        )

    @staticmethod
    def _rule_from_row(row: sqlite3.Row) -> ReminderRule:
        repeat = row["repeat_every_minutes"]
        return ReminderRule(
            id=int(row["id"]),
            offset_minutes=int(row["offset_minutes"]),
            message_template=str(row["message_template"]),
            repeat_every_minutes=int(repeat) if repeat is not None else None,
            enabled=bool(row["enabled"]),
            sort_order=int(row["sort_order"]),
            led_enabled=bool(row["led_enabled"]),
            led_red=int(row["led_red"]),
            led_green=int(row["led_green"]),
            led_blue=int(row["led_blue"]),
            led_flash_interval_ms=int(row["led_flash_interval_ms"]),
            led_flash_duration_seconds=int(row["led_flash_duration_seconds"]),
            led_chase_duration_seconds=int(row["led_chase_duration_seconds"]),
            buzzer_enabled=bool(row["buzzer_enabled"]),
            buzzer_pitch_hz=int(row["buzzer_pitch_hz"]),
            buzzer_volume=int(row["buzzer_volume"]),
            buzzer_count=int(row["buzzer_count"]),
            buzzer_beep_ms=int(row["buzzer_beep_ms"]),
            buzzer_gap_ms=int(row["buzzer_gap_ms"]),
        )

    @staticmethod
    def _race_event_from_row(row: sqlite3.Row) -> RaceEvent:
        return RaceEvent(
            id=int(row["id"]),
            season_year=int(row["season_year"]),
            race_number=str(row["race_number"]),
            venue_label=str(row["venue_label"]),
            date_saturday=date.fromisoformat(str(row["date_saturday"])),
            date_sunday=date.fromisoformat(str(row["date_sunday"])),
            iyr_series_id=str(row["iyr_series_id"]),
            iyr_base_url=str(row["iyr_base_url"]),
            source_url=str(row["source_url"]),
            scraped_at=datetime.fromisoformat(str(row["scraped_at"])),
        )

    @staticmethod
    def _iyr_session_from_row(row: sqlite3.Row) -> IyrRaceSession:
        return IyrRaceSession(
            id=int(row["id"]),
            race_event_id=int(row["race_event_id"]),
            iyr_eid=str(row["iyr_eid"]),
            category_label=str(row["category_label"]),
            race_date=date.fromisoformat(str(row["race_date"])),
            results_url=str(row["results_url"]),
            results_status=str(row["results_status"]),
            scraped_at=datetime.fromisoformat(str(row["scraped_at"])),
        )

    @staticmethod
    def _race_result_from_row(row: sqlite3.Row) -> RaceResult:
        return RaceResult(
            id=int(row["id"]),
            participant_id=int(row["participant_id"]),
            iyr_session_id=int(row["iyr_session_id"]),
            place=int(row["place"]),
            bib=row["bib"],
            team_name=row["team_name"],
            laps=int(row["laps"]) if row["laps"] is not None else None,
            total_time=row["total_time"],
            total_distance=row["total_distance"],
            raw_name=str(row["raw_name"]),
            match_confidence=float(row["match_confidence"]),
            match_method=str(row["match_method"]),
            result_status=str(row["result_status"]),
            fetched_at=datetime.fromisoformat(str(row["fetched_at"])),
        )
