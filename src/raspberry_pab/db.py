"""SQLite storage for schedules, reminder rules, and fired alerts."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from raspberry_pab.models import (
    Alert,
    Participant,
    ParticipantCreate,
    ParticipantUpdate,
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
                """
            )
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
                   enabled, sort_order
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
                       enabled, sort_order
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
        )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE reminder_rules
                SET offset_minutes = ?, message_template = ?,
                    repeat_every_minutes = ?, enabled = ?, sort_order = ?
                WHERE id = ?
                """,
                (
                    merged.offset_minutes,
                    merged.message_template.strip(),
                    merged.repeat_every_minutes,
                    int(merged.enabled),
                    merged.sort_order,
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
    def _create_rules(
        conn: sqlite3.Connection, rules: Iterable[ReminderRuleCreate]
    ) -> sqlite3.Cursor:
        cursor = conn.cursor()
        for rule in rules:
            cursor.execute(
                """
                INSERT INTO reminder_rules
                    (offset_minutes, message_template, repeat_every_minutes,
                     enabled, sort_order)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    rule.offset_minutes,
                    rule.message_template.strip(),
                    rule.repeat_every_minutes,
                    int(rule.enabled),
                    rule.sort_order,
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
        )
