"""Background reminder scheduler, alert broadcast broker, and race-results sync."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime

from pydantic import TypeAdapter

from raspberry_pab.db import ScheduleStore
from raspberry_pab.kiosk_clock import effective_now
from raspberry_pab.models import Alert
from raspberry_pab.race_results.window import (
    DEFAULT_RESULTS_SYNC_MINUTES,
    RESULTS_SYNC_INTERVAL_KEY,
    read_interval_minutes,
    results_sync_window,
)
from raspberry_pab.reminders import build_due_alerts

logger = logging.getLogger(__name__)
_ALERT_ADAPTER = TypeAdapter(Alert)


class AlertBroker:
    """In-process pub/sub for kiosk alert overlays."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Alert]] = set()
        self.active_alert: Alert | None = None
        self._before_publish: list = []

    def add_before_publish(self, callback) -> None:
        """Register an async callback invoked before each alert is broadcast."""
        self._before_publish.append(callback)

    async def publish(self, alert: Alert) -> None:
        for callback in self._before_publish:
            try:
                result = callback(alert)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("Alert broker before_publish callback failed")
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
        queue: asyncio.Queue[Alert] = asyncio.Queue(maxsize=32)
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
        current = now or effective_now(self.store)
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


class RaceResultsSyncScheduler:
    """Periodically syncs race results in the background during the race window."""

    def __init__(
        self,
        store: ScheduleStore,
        interval_minutes: int = DEFAULT_RESULTS_SYNC_MINUTES,
    ) -> None:
        self._store = store
        self._default_interval = interval_minutes
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    @property
    def interval_minutes(self) -> int:
        if self._store.get_setting(RESULTS_SYNC_INTERVAL_KEY) is None:
            return self._default_interval
        return read_interval_minutes(self._store)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event = asyncio.Event()
            self._task = asyncio.create_task(
                self._run(), name="race-results-sync-scheduler"
            )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            interval = self.interval_minutes
            if interval <= 0:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=60)
                except TimeoutError:
                    pass
                continue
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=interval * 60,
                )
            except TimeoutError:
                pass
            if self._stop_event.is_set():
                break
            try:
                await asyncio.to_thread(self._sync_today)
            except Exception:
                logger.exception("Race results sync tick failed")

    def _sync_today(self) -> None:
        from raspberry_pab.race_results.sync import RaceResultsSync

        now = effective_now(self._store)
        window = results_sync_window(self._store, now)
        if not window.active:
            logger.info(
                "Race results auto-sync skipped outside window for %s "
                "(start=%s end=%s)",
                now.date(),
                window.window_start,
                window.window_end,
            )
            return

        sync = RaceResultsSync(self._store)
        try:
            sync.sync_date(now.date())
            logger.info("Race results auto-sync complete for %s", now.date())
        finally:
            sync.close()


def sse_payload(alert: Alert) -> str:
    data = json.dumps(_ALERT_ADAPTER.dump_python(alert, mode="json"))
    return f"event: alert\ndata: {data}\n\n"
