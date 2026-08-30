"""Tests for same-time alert batching and sequential playback."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time

from raspberry_pab.alert_batch import (
    drain_alert_queue,
    group_alerts_by_slot,
)
from raspberry_pab.config import Settings
from raspberry_pab.matrix_controller import MatrixController
from raspberry_pab.models import Alert, ReminderRule
from raspberry_pab.server import play_alert_groups


class MockSerial:
    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.closed = False
        self._reads = [
            b"READY\n",
            b"PONG\n",
            b"OK\n",
            b"OK\n",
        ]

    def readline(self) -> bytes:
        if self._reads:
            return self._reads.pop(0)
        return b""

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        return len(data)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def _alert(
    *,
    alert_id: str,
    participant_id: int,
    rule_id: int,
    name: str,
    fire_at: datetime,
    message: str,
) -> Alert:
    return Alert(
        id=alert_id,
        participant_id=participant_id,
        rule_id=rule_id,
        name=name,
        event_date=date(2026, 8, 29),
        start_time=time(12, 0),
        start_at=datetime(2026, 8, 29, 12, 0),
        fire_at=fire_at,
        message=message,
        created_at=datetime(2026, 8, 29, 11, 30),
    )


def test_group_alerts_by_slot_preserves_order() -> None:
    fire = datetime(2026, 8, 29, 11, 30)
    later = datetime(2026, 8, 29, 11, 45)
    alerts = [
        _alert(
            alert_id="1",
            participant_id=1,
            rule_id=1,
            name="Ada",
            fire_at=fire,
            message="Warm Up Ada",
        ),
        _alert(
            alert_id="2",
            participant_id=2,
            rule_id=1,
            name="Bea",
            fire_at=fire,
            message="Warm Up Bea",
        ),
        _alert(
            alert_id="3",
            participant_id=3,
            rule_id=2,
            name="Cal",
            fire_at=fire,
            message="Go Cal",
        ),
        _alert(
            alert_id="4",
            participant_id=1,
            rule_id=1,
            name="Ada",
            fire_at=later,
            message="Start Ada",
        ),
    ]
    groups = group_alerts_by_slot(alerts)
    assert len(groups) == 3
    assert [a.name for a in groups[0]] == ["Ada", "Bea"]
    assert [a.name for a in groups[1]] == ["Cal"]
    assert [a.name for a in groups[2]] == ["Ada"]


def test_drain_alert_queue() -> None:
    async def run() -> None:
        queue: asyncio.Queue[Alert] = asyncio.Queue()
        first = _alert(
            alert_id="1",
            participant_id=1,
            rule_id=1,
            name="Ada",
            fire_at=datetime(2026, 8, 29, 11, 30),
            message="Warm Up Ada",
        )
        second = _alert(
            alert_id="2",
            participant_id=2,
            rule_id=1,
            name="Bea",
            fire_at=datetime(2026, 8, 29, 11, 30),
            message="Warm Up Bea",
        )
        queue.put_nowait(second)
        drained = drain_alert_queue(queue, first)
        assert [a.name for a in drained] == ["Ada", "Bea"]
        assert queue.empty()

    asyncio.run(run())


def test_show_sequence_scrolls_each_message() -> None:
    async def run() -> None:
        serial = MockSerial()
        serial._reads = [
            b"READY\n",
            b"PONG\n",
            b"OK\n",
            b"OK\n",
            b"READY\n",
            b"PONG\n",
            b"OK\n",
            b"OK\n",
        ]

        def factory(_settings: Settings, _port: str) -> MockSerial:
            return serial

        controller = MatrixController(
            Settings(
                matrix_enabled=True,
                buzzer_port="/dev/ttyUSB0",
                matrix_brightness=64,
            ),
            serial_factory=factory,
        )
        rule = ReminderRule(
            id=1,
            offset_minutes=30,
            message_template="Warm Up {name}",
            led_enabled=True,
            led_red=255,
            led_green=0,
            led_blue=0,
            led_flash_duration_seconds=3,
            led_chase_duration_seconds=2,
            matrix_effect="solid",
        )
        await controller.show_sequence(rule, ["Warm Up Ada", "Warm Up Bea"])
        await controller.shutdown()
        scrolls = [w for w in serial.writes if w.startswith(b"SCROLL ")]
        assert scrolls == [
            b"SCROLL 255 0 0 5000 0 Warm Up Ada\n",
            b"SCROLL 255 0 0 5000 0 Warm Up Bea\n",
        ]

    asyncio.run(run())


def test_play_alert_groups_effects_once_matrix_sequence() -> None:
    async def run() -> None:
        fire = datetime(2026, 8, 29, 11, 30)
        groups = [
            [
                _alert(
                    alert_id="1",
                    participant_id=1,
                    rule_id=7,
                    name="Ada",
                    fire_at=fire,
                    message="Warm Up Ada",
                ),
                _alert(
                    alert_id="2",
                    participant_id=2,
                    rule_id=7,
                    name="Bea",
                    fire_at=fire,
                    message="Warm Up Bea",
                ),
            ]
        ]
        rule = ReminderRule(
            id=7,
            offset_minutes=30,
            message_template="Warm Up {name}",
            led_enabled=True,
            led_red=1,
            led_green=2,
            led_blue=3,
            led_flash_duration_seconds=1,
            led_chase_duration_seconds=0,
        )

        class FakeStore:
            def get_rule(self, rule_id: int) -> ReminderRule | None:
                return rule if rule_id == 7 else None

        class Counter:
            def __init__(self) -> None:
                self.calls = 0

            async def flash(self, _rule: ReminderRule) -> None:
                self.calls += 1

            async def beep(self, _rule: ReminderRule) -> None:
                self.calls += 1

            async def play(self, _rule: ReminderRule) -> None:
                self.calls += 1

        class FakeMatrix:
            def __init__(self) -> None:
                self.sequences: list[list[str]] = []

            async def show_sequence(
                self, _rule: ReminderRule, messages: list[str]
            ) -> None:
                self.sequences.append(messages)

        led = Counter()
        buzzer = Counter()
        sound = Counter()
        matrix = FakeMatrix()
        await play_alert_groups(
            groups,
            store=FakeStore(),  # type: ignore[arg-type]
            led_controller=led,  # type: ignore[arg-type]
            matrix_controller=matrix,  # type: ignore[arg-type]
            buzzer_controller=buzzer,  # type: ignore[arg-type]
            sound_controller=sound,  # type: ignore[arg-type]
        )
        assert led.calls == 1
        assert buzzer.calls == 1
        assert sound.calls == 1
        assert matrix.sequences == [["Warm Up Ada", "Warm Up Bea"]]

    asyncio.run(run())
