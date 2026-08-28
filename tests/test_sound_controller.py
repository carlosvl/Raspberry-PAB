"""Tests for HDMI sound controller behavior."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from raspberry_pab.config import Settings
from raspberry_pab.models import ReminderRule
from raspberry_pab.sound_controller import SoundController, build_play_command


class MockProcess:
    def __init__(self, *, block: bool = False) -> None:
        self.terminated = False
        self.killed = False
        self._returncode: int | None = None
        self._release = threading.Event()
        self._block = block
        if not block:
            self._returncode = 0
            self._release.set()

    def poll(self) -> int | None:
        return self._returncode

    def terminate(self) -> None:
        self.terminated = True
        self._returncode = -15
        self._release.set()

    def kill(self) -> None:
        self.killed = True
        self._returncode = -9
        self._release.set()

    def wait(self, timeout: float | None = None) -> int:
        if self._block and self._returncode is None:
            self._release.wait(timeout if timeout is not None else 30)
        if self._returncode is None:
            self._returncode = 0
        return self._returncode


def _enabled_rule(**overrides: object) -> ReminderRule:
    values: dict[str, object] = {
        "id": 1,
        "offset_minutes": 30,
        "message_template": "Warm Up {name}",
        "sound_enabled": True,
        "sound_id": 7,
        "sound_volume": 80,
    }
    values.update(overrides)
    return ReminderRule(**values)  # type: ignore[arg-type]


def test_build_play_command_pw_play(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "7.wav"
    path.write_bytes(b"RIFF")
    monkeypatch.setattr(
        "raspberry_pab.sound_controller.shutil.which",
        lambda name: "/usr/bin/pw-play" if name == "pw-play" else None,
    )
    command, _env = build_play_command(
        path=path,
        volume=50,
        sink="alsa_output.platform-fef00700.hdmi.hdmi-stereo",
    )
    assert command[0] == "pw-play"
    assert "--volume=0.5" in command
    assert "--target" in command
    assert "alsa_output.platform-fef00700.hdmi.hdmi-stereo" in command
    assert str(path) in command


def test_play_skips_when_globally_disabled(tmp_path: Path) -> None:
    async def run() -> None:
        calls: list[list[str]] = []

        def factory(command: list[str], _env: dict[str, str]) -> MockProcess:
            calls.append(command)
            return MockProcess()

        path = tmp_path / "7.wav"
        path.write_bytes(b"RIFF")
        controller = SoundController(
            Settings(sound_enabled=False),
            path_resolver=lambda _sid: path,
            player_factory=factory,
            sink_resolver=lambda _s: "hdmi-sink",
        )
        await controller.play(_enabled_rule())
        await controller.shutdown()
        assert calls == []

    asyncio.run(run())


def test_play_skips_when_rule_disabled(tmp_path: Path) -> None:
    async def run() -> None:
        calls: list[list[str]] = []

        def factory(command: list[str], _env: dict[str, str]) -> MockProcess:
            calls.append(command)
            return MockProcess()

        path = tmp_path / "7.wav"
        path.write_bytes(b"RIFF")
        controller = SoundController(
            Settings(sound_enabled=True),
            path_resolver=lambda _sid: path,
            player_factory=factory,
            sink_resolver=lambda _s: "hdmi-sink",
        )
        await controller.play(_enabled_rule(sound_enabled=False))
        await controller.shutdown()
        assert calls == []

    asyncio.run(run())


def test_play_once_and_cancel_previous(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "raspberry_pab.sound_controller.shutil.which",
        lambda name: f"/usr/bin/{name}" if name in {"pw-play", "paplay"} else None,
    )

    async def run() -> None:
        processes: list[MockProcess] = []

        def factory(_command: list[str], _env: dict[str, str]) -> MockProcess:
            process = MockProcess(block=True)
            processes.append(process)
            return process

        path = tmp_path / "7.wav"
        path.write_bytes(b"RIFF")
        controller = SoundController(
            Settings(sound_enabled=True),
            path_resolver=lambda _sid: path,
            player_factory=factory,
            sink_resolver=lambda _s: "hdmi-sink",
        )
        await controller.play(_enabled_rule(sound_volume=40))
        await asyncio.sleep(0.05)
        assert len(processes) == 1
        first = processes[0]
        await controller.play(_enabled_rule(sound_volume=90))
        await asyncio.sleep(0.05)
        assert first.terminated is True
        assert len(processes) == 2
        await controller.shutdown()
        assert processes[1].terminated is True

    asyncio.run(run())
