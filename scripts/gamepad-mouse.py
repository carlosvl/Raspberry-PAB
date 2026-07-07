#!/usr/bin/env python3
"""Map a USB gamepad stick and buttons to X11 mouse movement and clicks."""

from __future__ import annotations

import glob
import os
import select
import struct
import subprocess
import sys
import time

DISPLAY = os.environ.get("DISPLAY", ":0")
SENS = float(os.environ.get("PAB_GAMEPAD_SENS", "8"))
DEADZONE = float(os.environ.get("PAB_GAMEPAD_DEADZONE", "0.15"))
DEVICE_OVERRIDE = os.environ.get("PAB_GAMEPAD_DEVICE", "auto")
LOG_PATH = "/tmp/gamepad-mouse.log"

JS_EVENT_FORMAT = "IhBB"
JS_EVENT_SIZE = struct.calcsize(JS_EVENT_FORMAT)
POLL_SECONDS = 0.03
AXIS_MAX = 32767.0
CLICK_PAUSE_SECONDS = 0.12
click_paused_until = 0.0

JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80

AXIS_X = 0
AXIS_Y = 1
HAT_X = 6
HAT_Y = 7
BTN_LEFT = int(os.environ.get("PAB_GAMEPAD_BTN_LEFT", "1"))
BTN_RIGHT = int(os.environ.get("PAB_GAMEPAD_BTN_RIGHT", "2"))

# Common d-pad-as-button layouts on generic USB pads.
DPAD_BUTTON_VECTORS: dict[int, tuple[int, int]] = {
    4: (0, -1),
    5: (0, 1),
    6: (-1, 0),
    7: (1, 0),
}


def log(message: str) -> None:
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {message}\n")


def find_gamepad_device() -> str | None:
    if DEVICE_OVERRIDE and DEVICE_OVERRIDE != "auto":
        return DEVICE_OVERRIDE if os.path.exists(DEVICE_OVERRIDE) else None

    try:
        from raspberry_pab.gamepad_config import find_gamepad_js_device

        return find_gamepad_js_device()
    except ImportError:
        pass

    for path in sorted(glob.glob("/dev/input/js*")):
        try:
            name_path = f"/sys/class/input/{os.path.basename(path)}/device/name"
            with open(name_path, encoding="utf-8") as handle:
                name = handle.read().lower()
            if "gamepad" in name or "joystick" in name or "controller" in name:
                return path
        except OSError:
            continue
    if os.path.exists("/dev/input/js0"):
        return "/dev/input/js0"
    return None


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*args],
        env={**os.environ, "DISPLAY": DISPLAY},
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def xdotool(*args: str) -> None:
    run("xdotool", *args)


def axis_delta(value: int) -> int:
    normalized = value / AXIS_MAX
    if abs(normalized) < DEADZONE:
        return 0
    scaled = (abs(normalized) - DEADZONE) / (1.0 - DEADZONE)
    direction = 1 if normalized > 0 else -1
    return int(round(direction * scaled * SENS))


class GamepadState:
    def __init__(self) -> None:
        self.axis_values: dict[int, int] = {}
        self.held_buttons: set[int] = set()

    def set_axis(self, number: int, value: int) -> None:
        self.axis_values[number] = value

    def set_button(self, number: int, pressed: bool) -> None:
        if pressed:
            self.held_buttons.add(number)
        else:
            self.held_buttons.discard(number)

    def movement(self) -> tuple[int, int]:
        dx = axis_delta(self.axis_values.get(AXIS_X, 0))
        dy = axis_delta(self.axis_values.get(AXIS_Y, 0))

        hat_dx = axis_delta(self.axis_values.get(HAT_X, 0))
        hat_dy = axis_delta(self.axis_values.get(HAT_Y, 0))
        if hat_dx or hat_dy:
            dx += hat_dx
            dy += hat_dy

        for number in self.held_buttons:
            vector = DPAD_BUTTON_VECTORS.get(number)
            if vector is None:
                continue
            btn_dx, btn_dy = vector
            if btn_dx:
                dx += int(round(btn_dx * SENS))
            if btn_dy:
                dy += int(round(btn_dy * SENS))

        return dx, dy


def synthetic_left_click(_state: GamepadState) -> None:
    global click_paused_until
    click_paused_until = time.monotonic() + CLICK_PAUSE_SECONDS
    xdotool("mousedown", "1")
    xdotool("mouseup", "1")
    click_paused_until = time.monotonic() + CLICK_PAUSE_SECONDS


def handle_button(state: GamepadState, number: int, pressed: bool) -> None:
    state.set_button(number, pressed)
    if not pressed:
        return
    if number == BTN_LEFT:
        synthetic_left_click(state)
    elif number == BTN_RIGHT:
        xdotool("click", "3")


def apply_movement(state: GamepadState) -> None:
    if time.monotonic() < click_paused_until:
        return
    dx, dy = state.movement()
    if dx or dy:
        xdotool("mousemove_relative", "--", str(dx), str(dy))


def drain_events(fd: int, state: GamepadState) -> None:
    while True:
        ready, _, _ = select.select([fd], [], [], 0)
        if not ready:
            break
        data = os.read(fd, JS_EVENT_SIZE)
        if len(data) < JS_EVENT_SIZE:
            break

        _timestamp, value, event_type, number = struct.unpack(JS_EVENT_FORMAT, data)
        base_type = event_type & ~JS_EVENT_INIT

        if base_type == JS_EVENT_BUTTON:
            handle_button(state, number, value != 0)
        elif base_type == JS_EVENT_AXIS:
            state.set_axis(number, value)


def main() -> None:
    device = find_gamepad_device()
    if device is None:
        log("no gamepad device found; exiting")
        sys.exit(0)

    log(f"using {device} sens={SENS} deadzone={DEADZONE} display={DISPLAY}")
    fd = os.open(device, os.O_RDONLY)
    state = GamepadState()

    while True:
        ready, _, _ = select.select([fd], [], [], POLL_SECONDS)
        if ready:
            drain_events(fd, state)
        apply_movement(state)


if __name__ == "__main__":
    main()
