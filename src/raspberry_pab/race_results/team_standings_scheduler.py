"""Background poller for live MCA team standings (ticker + matrix)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from raspberry_pab.db import ScheduleStore
from raspberry_pab.kiosk_clock import effective_now
from raspberry_pab.matrix_controller import MatrixController
from raspberry_pab.race_results.client import FetchText
from raspberry_pab.race_results.team_standings_live import (
    LiveStandingsSnapshot,
    read_enabled,
    read_interval_minutes,
    read_series_url,
    read_team,
    refresh_live_standings,
)

logger = logging.getLogger(__name__)


class TeamStandingsScheduler:
    """Poll IYR, cache standings, and SCROLLONCE the matrix on an interval."""

    def __init__(
        self,
        store: ScheduleStore,
        *,
        matrix_controller: MatrixController | None = None,
        alerts_busy: asyncio.Event | None = None,
        fetch_text: FetchText | None = None,
    ) -> None:
        self._store = store
        self._matrix = matrix_controller
        self._alerts_busy = alerts_busy
        self._fetch_text = fetch_text
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._snapshot: LiveStandingsSnapshot | None = None
        self._matrix_rotation = 0

    @property
    def snapshot(self) -> LiveStandingsSnapshot | None:
        return self._snapshot

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event = asyncio.Event()
            self._task = asyncio.create_task(
                self._run(), name="team-standings-scheduler"
            )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task

    async def refresh_now(self) -> LiveStandingsSnapshot:
        return await asyncio.to_thread(self._refresh_sync)

    def _refresh_sync(self) -> LiveStandingsSnapshot:
        series_url = read_series_url(self._store)
        focus_team = read_team(self._store)
        scraped_at = datetime.now(UTC).astimezone()
        try:
            snapshot = refresh_live_standings(
                series_url=series_url,
                focus_team=focus_team,
                scraped_at=scraped_at,
                fetch_text=self._fetch_text,
            )
        except Exception as exc:
            logger.exception("Live team standings refresh failed")
            snapshot = LiveStandingsSnapshot(
                series_url=series_url,
                focus_team=focus_team,
                scraped_at=scraped_at,
                buckets=[],
                ticker_text="",
                matrix_messages=[],
                error=str(exc),
            )
        self._snapshot = snapshot
        return snapshot

    async def _run(self) -> None:
        # First refresh soon after boot so the ticker is not empty all race.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stop_event.wait(), timeout=15)
        if not self._stop_event.is_set():
            await self._tick()

        while not self._stop_event.is_set():
            interval = read_interval_minutes(self._store)
            if not read_enabled(self._store) or interval <= 0:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._stop_event.wait(), timeout=60)
                continue
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=interval * 60,
                )
            if self._stop_event.is_set():
                break
            await self._tick()

    async def _tick(self) -> None:
        if not read_enabled(self._store):
            return
        if read_interval_minutes(self._store) <= 0:
            return
        try:
            snapshot = await self.refresh_now()
            logger.info(
                "Live team standings refreshed (%d buckets) at %s",
                len(snapshot.buckets),
                effective_now(self._store).isoformat(),
            )
        except Exception:
            logger.exception("Live team standings tick failed")
            return
        await self._maybe_matrix(snapshot)

    async def _maybe_matrix(self, snapshot: LiveStandingsSnapshot) -> None:
        if self._matrix is None:
            return
        if self._alerts_busy is not None and self._alerts_busy.is_set():
            logger.info("Skipping team standings matrix while alerts busy")
            return
        messages = snapshot.matrix_messages
        if not messages:
            return
        index = self._matrix_rotation % len(messages)
        self._matrix_rotation += 1
        message = messages[index]
        try:
            await self._matrix.scroll_once(message, effect="solid")
        except Exception:
            logger.exception("Team standings matrix scroll failed")
