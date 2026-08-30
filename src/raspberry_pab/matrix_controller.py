"""Serial WS2812 matrix control for reminder alerts via Arduino Nano."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from collections.abc import Callable

from raspberry_pab.arduino_serial import (
    HARDWARE_SERIAL_LOCK,
    effective_matrix_port,
    handshake,
    open_serial_port,
    transact_line,
    wait_for_ok,
)
from raspberry_pab.config import Settings
from raspberry_pab.models import MATRIX_EFFECT_MODE, MatrixEffect, ReminderRule

logger = logging.getLogger(__name__)

SerialFactory = Callable[[Settings, str], object]

# Keep SCROLL under Nano's 64-byte RX:
# "SCROLL 255 255 255 20000 1 " is 26 chars → leave ~36 for text.
MAX_MATRIX_MESSAGE_CHARS = 36
_ALLOWED_MESSAGE_CHARS = re.compile(r"[^A-Za-z0-9 .,:!?\-_'#/@&()+%=]+")


def _default_serial_factory(settings: Settings, port: str) -> object:
    return open_serial_port(settings, port=port)


def sanitize_matrix_message(message: str) -> str:
    """Keep printable ASCII suitable for the 8x64 matrix font."""
    cleaned = _ALLOWED_MESSAGE_CHARS.sub(" ", message)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "PAB"
    return cleaned[:MAX_MATRIX_MESSAGE_CHARS]


def matrix_effect_mode(effect: MatrixEffect | str) -> int:
    return MATRIX_EFFECT_MODE.get(effect, 0)  # type: ignore[arg-type]


def build_bright_command(brightness: int) -> str:
    return f"BRIGHT {brightness}\n"


def build_solid_command(
    *,
    red: int,
    green: int,
    blue: int,
    duration_ms: int,
) -> str:
    return f"SOLID {red} {green} {blue} {duration_ms}\n"


def build_scroll_command(
    *,
    red: int,
    green: int,
    blue: int,
    duration_ms: int,
    message: str,
    effect: MatrixEffect | str = "solid",
) -> str:
    text = sanitize_matrix_message(message)
    mode = matrix_effect_mode(effect)
    return f"SCROLL {red} {green} {blue} {duration_ms} {mode} {text}\n"


def build_clear_command() -> str:
    return "CLEAR\n"


def build_scroll_once_command(
    *,
    red: int,
    green: int,
    blue: int,
    message: str,
    effect: MatrixEffect | str = "rainbow",
) -> str:
    text = sanitize_matrix_message(message)
    mode = matrix_effect_mode(effect)
    return f"SCROLLONCE {red} {green} {blue} {mode} {text}\n"


def build_rainbow_command(*, duration_ms: int) -> str:
    return f"RAINBOW {max(duration_ms, 1)}\n"


def matrix_display_duration_ms(rule: ReminderRule) -> int:
    """Total time to hold the matrix on for a reminder."""
    total_seconds = rule.led_flash_duration_seconds + max(
        0, rule.led_chase_duration_seconds
    )
    return max(total_seconds, 1) * 1000


class MatrixController:
    """Drives a WS2812 matrix over USB serial when reminder rules fire."""

    def __init__(
        self,
        settings: Settings,
        *,
        serial_factory: SerialFactory | None = None,
        hardware_lock: asyncio.Lock | None = None,
    ) -> None:
        self._settings = settings
        self._serial_factory = serial_factory or _default_serial_factory
        self._hardware_lock = hardware_lock or HARDWARE_SERIAL_LOCK
        self._lock = asyncio.Lock()
        self._show_task: asyncio.Task[None] | None = None

    async def show(self, rule: ReminderRule, message: str) -> None:
        if not self._should_show(rule):
            return
        await self._start_show(rule, message)

    async def show_sequence(self, rule: ReminderRule, messages: list[str]) -> None:
        """Scroll each message in order without cancelling mid-sequence."""
        if not self._should_show(rule):
            return
        cleaned = [message for message in messages if message.strip()]
        if not cleaned:
            return
        if self._show_task and not self._show_task.done():
            self._show_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._show_task
        self._show_task = asyncio.create_task(
            self._run_show_sequence(rule, cleaned),
            name="matrix-show-sequence",
        )
        await self._show_task

    async def flash(self, rule: ReminderRule) -> None:
        """Backward-compatible entry point for alert listener."""
        await self.show(rule, rule.message_template)

    async def show_test(
        self,
        *,
        message: str,
        led_red: int,
        led_green: int,
        led_blue: int,
        led_flash_duration_seconds: int,
        led_chase_duration_seconds: int = 0,
        matrix_effect: MatrixEffect = "solid",
    ) -> None:
        if not self._settings.matrix_enabled or not effective_matrix_port(
            self._settings
        ):
            return
        rule = ReminderRule(
            id=0,
            offset_minutes=0,
            message_template=message,
            led_enabled=True,
            led_red=led_red,
            led_green=led_green,
            led_blue=led_blue,
            led_flash_duration_seconds=led_flash_duration_seconds,
            led_chase_duration_seconds=led_chase_duration_seconds,
            matrix_effect=matrix_effect,
        )
        await self._start_show(rule, message, wait=True)

    async def flash_test(
        self,
        *,
        led_red: int,
        led_green: int,
        led_blue: int,
        led_flash_interval_ms: int,
        led_flash_duration_seconds: int,
        led_chase_duration_seconds: int = 10,
        message: str = "Matrix test",
        matrix_effect: MatrixEffect = "solid",
    ) -> None:
        await self.show_test(
            message=message,
            led_red=led_red,
            led_green=led_green,
            led_blue=led_blue,
            led_flash_duration_seconds=led_flash_duration_seconds,
            led_chase_duration_seconds=led_chase_duration_seconds,
            matrix_effect=matrix_effect,
        )

    async def stop(self) -> None:
        """Cancel any in-progress matrix show."""
        if self._show_task and not self._show_task.done():
            self._show_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._show_task
        self._show_task = None

    async def rainbow_pulse(
        self,
        *,
        pulse_ms: int = 500,
        stop_event: asyncio.Event,
        message: str = "MUSIC BREAK",
    ) -> None:
        """Loop rainbow scrolling text until stop_event is set (music-break mode)."""
        if not self._settings.matrix_enabled or not effective_matrix_port(
            self._settings
        ):
            await stop_event.wait()
            return
        await self.stop()
        self._show_task = asyncio.create_task(
            self._run_rainbow_scroll(
                pulse_ms=pulse_ms,
                stop_event=stop_event,
                message=message,
            ),
            name="matrix-rainbow-scroll",
        )

    async def shutdown(self) -> None:
        await self.stop()

    async def _start_show(
        self,
        rule: ReminderRule,
        message: str,
        *,
        wait: bool = False,
    ) -> None:
        if self._show_task and not self._show_task.done():
            self._show_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._show_task
        self._show_task = asyncio.create_task(
            self._run_show(rule, message),
            name="matrix-show",
        )
        if wait:
            await self._show_task

    def _should_show(self, rule: ReminderRule) -> bool:
        return (
            self._settings.matrix_enabled
            and bool(effective_matrix_port(self._settings))
            and rule.led_enabled
        )

    async def _run_show(self, rule: ReminderRule, message: str) -> None:
        async with self._lock:
            try:
                async with self._hardware_lock:
                    await asyncio.to_thread(
                        self._execute_show_sequence,
                        rule,
                        message,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Matrix show failed for rule %s", rule.id)

    async def _run_show_sequence(
        self,
        rule: ReminderRule,
        messages: list[str],
    ) -> None:
        async with self._lock:
            try:
                async with self._hardware_lock:
                    for message in messages:
                        await asyncio.to_thread(
                            self._execute_show_sequence,
                            rule,
                            message,
                        )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Matrix show sequence failed for rule %s", rule.id
                )

    async def _run_rainbow_scroll(
        self,
        *,
        pulse_ms: int,
        stop_event: asyncio.Event,
        message: str,
    ) -> None:
        # Full-panel rainbow after each completed text pass.
        fill_ms = max(pulse_ms * 6, 3000)
        try:
            while not stop_event.is_set():
                async with self._lock:
                    async with self._hardware_lock:
                        await asyncio.to_thread(
                            self._execute_scroll_once,
                            message,
                            "rainbow",
                        )
                if stop_event.is_set():
                    break
                async with self._lock:
                    async with self._hardware_lock:
                        await asyncio.to_thread(
                            self._execute_rainbow_fill,
                            fill_ms,
                        )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Matrix rainbow scroll failed")

    def _execute_scroll_once(
        self,
        message: str,
        effect: MatrixEffect | str,
    ) -> None:
        display_message = sanitize_matrix_message(message)
        port_name = effective_matrix_port(self._settings)
        # One full pass across 8x96: width + text width, ~50ms/frame.
        char_w = 6
        text_w = max(len(display_message), 1) * char_w
        pass_ms = (self._settings.matrix_width + text_w) * 50
        logger.info(
            "Matrix scroll-once (%s, ~%d ms): %s",
            effect,
            pass_ms,
            display_message,
        )
        port = self._serial_factory(self._settings, port_name)
        try:
            handshake(port)
            bright_cmd = build_bright_command(self._settings.matrix_brightness)
            if transact_line(port, bright_cmd, {"OK"}, attempts=3) != "OK":
                raise RuntimeError("Arduino did not accept BRIGHT command")
            scroll_cmd = build_scroll_once_command(
                red=255,
                green=255,
                blue=255,
                message=display_message,
                effect=effect,
            )
            port.write(scroll_cmd.encode("ascii"))
            port.flush()
            timeout = max(pass_ms / 1000.0 * 2.0 + 5.0, 20.0)
            if not wait_for_ok(port, timeout=timeout):
                raise RuntimeError("Arduino did not finish SCROLLONCE command")
        finally:
            with contextlib.suppress(Exception):
                port.write(build_clear_command().encode("ascii"))
                port.flush()
            port.close()

    def _execute_rainbow_fill(self, duration_ms: int) -> None:
        port_name = effective_matrix_port(self._settings)
        logger.info("Matrix rainbow fill (%d ms)", duration_ms)
        port = self._serial_factory(self._settings, port_name)
        try:
            handshake(port)
            bright_cmd = build_bright_command(self._settings.matrix_brightness)
            if transact_line(port, bright_cmd, {"OK"}, attempts=3) != "OK":
                raise RuntimeError("Arduino did not accept BRIGHT command")
            cmd = build_rainbow_command(duration_ms=duration_ms)
            port.write(cmd.encode("ascii"))
            port.flush()
            timeout = max(duration_ms / 1000.0 * 2.0 + 5.0, 10.0)
            if not wait_for_ok(port, timeout=timeout):
                raise RuntimeError("Arduino did not finish RAINBOW command")
        finally:
            with contextlib.suppress(Exception):
                port.write(build_clear_command().encode("ascii"))
                port.flush()
            port.close()

    def _execute_show_sequence(self, rule: ReminderRule, message: str) -> None:
        duration_ms = matrix_display_duration_ms(rule)
        display_message = sanitize_matrix_message(message)
        port_name = effective_matrix_port(self._settings)
        logger.info(
            "Matrix scroll for rule %s (%d ms, %s): %s",
            rule.id,
            duration_ms,
            rule.matrix_effect,
            display_message,
        )
        port = self._serial_factory(self._settings, port_name)
        try:
            handshake(port)

            bright_cmd = build_bright_command(self._settings.matrix_brightness)
            bright_ok = transact_line(port, bright_cmd, {"OK"}, attempts=3)
            if bright_ok != "OK":
                raise RuntimeError("Arduino did not accept BRIGHT command")

            scroll_cmd = build_scroll_command(
                red=rule.led_red,
                green=rule.led_green,
                blue=rule.led_blue,
                duration_ms=duration_ms,
                message=display_message,
                effect=rule.matrix_effect,
            )
            port.write(scroll_cmd.encode("ascii"))
            port.flush()
            # NeoPixel show() disables interrupts on AVR, so wall time is
            # longer than the requested duration (~1.3x). Keep headroom.
            scroll_timeout = max(duration_ms / 1000.0 * 2.0 + 5.0, 15.0)
            scroll_ok = wait_for_ok(port, timeout=scroll_timeout)
            if not scroll_ok:
                raise RuntimeError("Arduino did not finish SCROLL command")
        finally:
            with contextlib.suppress(Exception):
                port.write(build_clear_command().encode("ascii"))
                port.flush()
            port.close()
