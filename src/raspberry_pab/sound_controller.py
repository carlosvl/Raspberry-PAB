"""Play reminder sound files once over HDMI via PipeWire/PulseAudio."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from raspberry_pab.config import Settings
from raspberry_pab.models import ReminderRule, SoundFile

logger = logging.getLogger(__name__)

PlayerFactory = Callable[[list[str], dict[str, str]], subprocess.Popen[bytes]]
SinkResolver = Callable[[Settings], str | None]
SoundPathResolver = Callable[[int], Path | None]


def _default_player(command: list[str], env: dict[str, str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def resolve_hdmi_sink(settings: Settings) -> str | None:
    """Return a PipeWire/Pulse sink name that looks like HDMI audio."""
    if settings.sound_sink.strip():
        return settings.sound_sink.strip()

    env = os.environ.copy()
    if "XDG_RUNTIME_DIR" not in env:
        runtime = Path(f"/run/user/{os.getuid()}")
        if runtime.is_dir():
            env["XDG_RUNTIME_DIR"] = str(runtime)

    if shutil.which("pactl"):
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[1]
            if "hdmi" in name.lower():
                return name

    return "alsa_output.platform-fef00700.hdmi.hdmi-stereo"


def build_play_command(
    *,
    path: Path,
    volume: int,
    sink: str | None,
) -> tuple[list[str], dict[str, str]]:
    env = os.environ.copy()
    if "XDG_RUNTIME_DIR" not in env:
        runtime = Path(f"/run/user/{os.getuid()}")
        if runtime.is_dir():
            env["XDG_RUNTIME_DIR"] = str(runtime)

    volume_f = max(0.0, min(1.0, volume / 100.0))

    if shutil.which("pw-play"):
        command = ["pw-play", f"--volume={volume_f}"]
        if sink:
            command.extend(["--target", sink])
        command.append(str(path))
        return command, env

    if shutil.which("paplay"):
        if sink:
            env["PULSE_SINK"] = sink
        command = ["paplay", f"--volume={int(volume_f * 65536)}", str(path)]
        return command, env

    raise RuntimeError("Neither pw-play nor paplay is available")


class SoundController:
    """Plays uploaded sound files once over HDMI for reminder alerts."""

    def __init__(
        self,
        settings: Settings,
        *,
        path_resolver: SoundPathResolver,
        player_factory: PlayerFactory | None = None,
        sink_resolver: SinkResolver | None = None,
    ) -> None:
        self._settings = settings
        self._path_resolver = path_resolver
        self._player_factory = player_factory or _default_player
        self._sink_resolver = sink_resolver or resolve_hdmi_sink
        self._lock = asyncio.Lock()
        self._play_task: asyncio.Task[None] | None = None
        self._process: subprocess.Popen[bytes] | None = None

    async def play(self, rule: ReminderRule) -> None:
        if not self._should_play(rule):
            return
        assert rule.sound_id is not None
        path = self._path_resolver(rule.sound_id)
        if path is None or not path.is_file():
            logger.warning("Sound file missing for sound_id=%s", rule.sound_id)
            return
        await self._start_play(path=path, volume=rule.sound_volume)

    async def play_file(
        self, path: Path, *, volume: int = 80, wait: bool = False
    ) -> None:
        if not self._settings.sound_enabled:
            return
        if not path.is_file():
            raise FileNotFoundError(str(path))
        await self._start_play(path=path, volume=volume, wait=wait)

    async def play_sound(
        self,
        sound: SoundFile,
        *,
        volume: int = 80,
        wait: bool = False,
    ) -> None:
        path = self._path_resolver(sound.id)
        if path is None:
            raise FileNotFoundError(sound.stored_name)
        await self.play_file(path, volume=volume, wait=wait)

    async def shutdown(self) -> None:
        await self._stop_current()

    def _should_play(self, rule: ReminderRule) -> bool:
        return (
            self._settings.sound_enabled
            and rule.sound_enabled
            and rule.sound_id is not None
        )

    async def _start_play(
        self,
        *,
        path: Path,
        volume: int,
        wait: bool = False,
    ) -> None:
        await self._stop_current()
        self._play_task = asyncio.create_task(
            self._run_play(path=path, volume=volume),
            name="hdmi-sound-play",
        )
        if wait:
            await self._play_task

    async def _stop_current(self) -> None:
        # Terminate the player first so a blocking wait() in a worker thread can
        # finish; asyncio cannot interrupt that thread by cancelling the task alone.
        self._terminate_process()
        if self._play_task and not self._play_task.done():
            self._play_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._play_task
        self._play_task = None

    def _terminate_process(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.poll() is None:
            with contextlib.suppress(ProcessLookupError, OSError):
                process.terminate()
            try:
                process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError, OSError):
                    process.kill()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=1.0)

    async def _run_play(self, *, path: Path, volume: int) -> None:
        async with self._lock:
            try:
                sink = self._sink_resolver(self._settings)
                command, env = build_play_command(path=path, volume=volume, sink=sink)
                self._process = await asyncio.to_thread(
                    self._player_factory, command, env
                )
                process = self._process
                try:
                    await asyncio.to_thread(process.wait)
                finally:
                    if self._process is process:
                        self._process = None
            except asyncio.CancelledError:
                self._terminate_process()
                raise
            except Exception:
                logger.exception("HDMI sound playback failed for %s", path)
                self._terminate_process()
