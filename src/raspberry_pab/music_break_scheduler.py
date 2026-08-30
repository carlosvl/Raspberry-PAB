"""Background scheduler for interval music breaks."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime
from pathlib import Path

from raspberry_pab.db import ScheduleStore
from raspberry_pab.kiosk_clock import effective_now
from raspberry_pab.led_controller import LedController
from raspberry_pab.matrix_controller import MatrixController
from raspberry_pab.music_breaks import (
    due_slot,
    load_config,
    mark_slot_fired,
    next_slot_after,
    was_slot_fired,
)
from raspberry_pab.sound_controller import SoundController

logger = logging.getLogger(__name__)


class MusicBreakScheduler:
    """Plays playlist tracks on an interval with rainbow LED/matrix animation."""

    def __init__(
        self,
        store: ScheduleStore,
        *,
        sound_controller: SoundController,
        led_controller: LedController,
        matrix_controller: MatrixController,
        sound_path_resolver,
        alerts_busy: asyncio.Event | None = None,
    ) -> None:
        self._store = store
        self._sound = sound_controller
        self._led = led_controller
        self._matrix = matrix_controller
        self._sound_path_resolver = sound_path_resolver
        self._alerts_busy = alerts_busy
        self._task: asyncio.Task[None] | None = None
        self._session_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._session_stop = asyncio.Event()
        self._playing = False

    @property
    def playing(self) -> bool:
        return self._playing

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event = asyncio.Event()
            self._task = asyncio.create_task(self._run(), name="music-break-scheduler")

    async def stop(self) -> None:
        self._stop_event.set()
        await self.interrupt()
        if self._task is not None:
            await self._task

    async def interrupt(self) -> None:
        """Stop song + animations immediately (e.g. when a reminder alert fires)."""
        self._session_stop.set()
        await self._sound.stop()
        await self._led.stop()
        await self._matrix.stop()
        if self._session_task and not self._session_task.done():
            self._session_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._session_task
        self._session_task = None
        self._playing = False

    def status_fields(self, now: datetime | None = None) -> dict[str, object]:
        current = now or effective_now(self._store)
        config = load_config(self._store)
        nxt = next_slot_after(current, config) if config.enabled else None
        return {
            "enabled": config.enabled,
            "interval_minutes": config.interval_minutes,
            "start_time": config.start_time,
            "sound_ids": list(config.sound_ids),
            "volume": config.volume,
            "pulse_ms": config.pulse_ms,
            "next_at": nxt.fire_at if nxt else None,
            "next_sound_id": nxt.sound_id if nxt else None,
            "next_slot": nxt.slot_index if nxt else None,
            "playing": self._playing,
            "kiosk_now": current,
        }

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.tick()
            except Exception:
                logger.exception("Music break scheduler tick failed")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=1)
            except TimeoutError:
                continue

    async def tick(self, now: datetime | None = None) -> bool:
        if self._playing:
            return False
        if self._alerts_busy is not None and self._alerts_busy.is_set():
            return False
        current = now or effective_now(self._store)
        config = load_config(self._store)
        slot = due_slot(current, config)
        if slot is None:
            return False
        if was_slot_fired(self._store, current.date(), slot.slot_index):
            return False
        mark_slot_fired(self._store, current.date(), slot.slot_index)
        self._session_task = asyncio.create_task(
            self._run_session(
                sound_id=slot.sound_id,
                volume=config.volume,
                pulse_ms=config.pulse_ms,
            ),
            name=f"music-break-slot-{slot.slot_index}",
        )
        return True

    async def run_test(self, *, duration_seconds: float = 10.0) -> None:
        """Admin test: play first playlist track (or silence animations only)."""
        await self.interrupt()
        config = load_config(self._store)
        if not config.sound_ids:
            raise ValueError("Playlist is empty")
        sound_id = config.sound_ids[0]
        self._session_task = asyncio.create_task(
            self._run_session(
                sound_id=sound_id,
                volume=config.volume,
                pulse_ms=config.pulse_ms,
                max_seconds=duration_seconds,
            ),
            name="music-break-test",
        )
        await self._session_task

    async def _run_session(
        self,
        *,
        sound_id: int,
        volume: int,
        pulse_ms: int,
        max_seconds: float | None = None,
    ) -> None:
        self._playing = True
        self._session_stop = asyncio.Event()
        path: Path | None = self._sound_path_resolver(sound_id)
        try:
            await self._led.rainbow_pulse(
                pulse_ms=pulse_ms,
                stop_event=self._session_stop,
            )
            await self._matrix.rainbow_pulse(
                pulse_ms=pulse_ms,
                stop_event=self._session_stop,
            )
            if path is not None and path.is_file():
                play_task = asyncio.create_task(
                    self._sound.play_file(path, volume=volume, wait=True),
                    name="music-break-audio",
                )
                waiters: list[asyncio.Task[object]] = [
                    asyncio.create_task(self._session_stop.wait()),
                    play_task,
                ]
                if max_seconds is not None:
                    waiters.append(asyncio.create_task(asyncio.sleep(max_seconds)))
                done, pending = await asyncio.wait(
                    waiters,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
                for task in done:
                    with contextlib.suppress(Exception):
                        task.result()
            elif max_seconds is not None:
                try:
                    await asyncio.wait_for(
                        self._session_stop.wait(),
                        timeout=max_seconds,
                    )
                except TimeoutError:
                    pass
            else:
                await self._session_stop.wait()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Music break session failed for sound_id=%s", sound_id)
        finally:
            self._session_stop.set()
            await self._sound.stop()
            await self._led.stop()
            await self._matrix.stop()
            self._playing = False
