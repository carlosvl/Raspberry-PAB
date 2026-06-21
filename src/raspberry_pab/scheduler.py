"""Background reminder scheduler and alert broadcast broker."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime

from pydantic import TypeAdapter

from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import Alert
from raspberry_pab.reminders import build_due_alerts

logger = logging.getLogger(__name__)
_ALERT_ADAPTER = TypeAdapter(Alert)


class AlertBroker:
    """In-process pub/sub for kiosk alert overlays."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Alert]] = set()
        self.active_alert: Alert | None = None

    async def publish(self, alert: Alert) -> None:
        self.active_alert = alert
        stale: list[asyncio.Queue[Alert]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(alert)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self._subscribers.discard(queue)

    @contextlib.asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[Alert]]:
        queue: asyncio.Queue[Alert] = asyncio.Queue(maxsize=10)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)


class ReminderScheduler:
    """Polls local schedules once per second and broadcasts due alerts."""

    def __init__(self, store: ScheduleStore, broker: AlertBroker) -> None:
        self.store = store
        self.broker = broker
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event = asyncio.Event()
            self._task = asyncio.create_task(self._run(), name="reminder-scheduler")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.tick()
            except Exception:
                logger.exception("Reminder scheduler tick failed")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=1)
            except TimeoutError:
                continue

    async def tick(self, now: datetime | None = None) -> list[Alert]:
        current = now or datetime.now()
        participants = self.store.list_participants(current.date())
        rules = self.store.list_rules(enabled_only=True)
        alerts = build_due_alerts(participants, rules, current)
        published: list[Alert] = []
        for alert in alerts:
            if not self.store.record_fired_alert(alert):
                continue
            await self.broker.publish(alert)
            published.append(alert)
        return published


def sse_payload(alert: Alert) -> str:
    data = json.dumps(_ALERT_ADAPTER.dump_python(alert, mode="json"))
    return f"event: alert\ndata: {data}\n\n"
