#!/usr/bin/env python3
"""Map a USB gamepad stick and buttons to X11 mouse movement and clicks."""

from __future__ import annotations

import glob
import os
import re
import select
import struct
import subprocess
import sys
import time

DISPLAY = os.environ.get("DISPLAY", ":0")
LOG_PATH = "/tmp/gamepad-mouse.log"
DEFAULT_TOUCH_MAP = os.path.expanduser("~/.config/raspberry-pab/touch-map.conf")

JS_EVENT_FORMAT = "IhBB"
JS_EVENT_SIZE = struct.calcsize(JS_EVENT_FORMAT)
POLL_SECONDS = 0.03
AXIS_MAX = 32767.0
CLICK_PAUSE_SECONDS = 0.12
click_paused_until = 0.0

SENS = 8.0
DEADZONE = 0.15
DEVICE_OVERRIDE = "auto"
EDGE_MARGIN = 16
SCROLL_SENS = 0.35
SCROLL_DELAY_MS = 10
BTN_LEFT = 1
BTN_RIGHT = 2

# Common d-pad-as-button layouts on generic USB pads.
DPAD_BUTTON_VECTORS: dict[int, tuple[int, int]] = {
    4: (0, -1),
    5: (0, 1),
    6: (-1, 0),
    7: (1, 0),
}


def read_touch_map_conf(path: str | None = None) -> dict[str, str]:
    conf_path = path or DEFAULT_TOUCH_MAP
    values: dict[str, str] = {}
    try:
        with open(conf_path, encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                values[key.strip()] = value.strip()
    except OSError:
        pass
    return values


def configure_from_touch_map(conf: dict[str, str] | None = None) -> None:
    """Load gamepad tuning from touch-map.conf; env vars override file values."""
    global SENS, DEADZONE, DEVICE_OVERRIDE, EDGE_MARGIN, SCROLL_SENS, SCROLL_DELAY_MS
    global BTN_LEFT, BTN_RIGHT

    file_vals = conf if conf is not None else read_touch_map_conf()

    def pick(key: str, default: str) -> str:
        return os.environ.get(key, file_vals.get(key, default))

    SENS = float(pick("PAB_GAMEPAD_SENS", "8"))
    DEADZONE = float(pick("PAB_GAMEPAD_DEADZONE", "0.15"))
    DEVICE_OVERRIDE = pick("PAB_GAMEPAD_DEVICE", "auto")
    EDGE_MARGIN = int(pick("PAB_GAMEPAD_EDGE_MARGIN", "16"))
    SCROLL_SENS = float(pick("PAB_GAMEPAD_SCROLL_SENS", "0.35"))
    SCROLL_DELAY_MS = int(pick("PAB_GAMEPAD_SCROLL_DELAY_MS", "10"))
    BTN_LEFT = int(pick("PAB_GAMEPAD_BTN_LEFT", "1"))
    BTN_RIGHT = int(pick("PAB_GAMEPAD_BTN_RIGHT", "2"))


JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80

AXIS_X = 0
AXIS_Y = 1
HAT_X = 6
HAT_Y = 7


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


def parse_mouse_location(text: str) -> tuple[int, int] | None:
    match = re.search(r"x:(\d+)\s+y:(\d+)", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def screen_size() -> tuple[int, int]:
    env_w = os.environ.get("PAB_GAMEPAD_SCREEN_W") or os.environ.get("PAB_TOUCH_SCREEN_W")
    env_h = os.environ.get("PAB_GAMEPAD_SCREEN_H") or os.environ.get("PAB_TOUCH_SCREEN_H")
    if env_w and env_h:
        return int(env_w), int(env_h)

    result = run("xdotool", "getdisplaygeometry")
    parts = result.stdout.strip().split()
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]), int(parts[1])
    return 1920, 1080


def clamp_pointer_move(
    x: int,
    y: int,
    dx: int,
    dy: int,
    *,
    screen_w: int,
    screen_h: int,
) -> tuple[int, int, int, int]:
    new_x = max(0, min(screen_w - 1, x + dx))
    new_y = max(0, min(screen_h - 1, y + dy))
    return new_x, new_y, dx - (new_x - x), dy - (new_y - y)


def edge_scroll_clicks(
    x: int,
    y: int,
    overflow_x: int,
    overflow_y: int,
    *,
    screen_w: int,
    screen_h: int,
    edge_margin: int = EDGE_MARGIN,
    scroll_sens: float = SCROLL_SENS,
    move_sens: float = SENS,
) -> tuple[int, int]:
    """Return (vertical_clicks, horizontal_clicks); negative means scroll up/left."""
    vertical = 0
    horizontal = 0

    if overflow_y > 0 and y >= screen_h - edge_margin:
        vertical = scroll_repeat_count(overflow_y, scroll_sens=scroll_sens, move_sens=move_sens)
    elif overflow_y < 0 and y <= edge_margin:
        vertical = -scroll_repeat_count(-overflow_y, scroll_sens=scroll_sens, move_sens=move_sens)

    if overflow_x > 0 and x >= screen_w - edge_margin:
        horizontal = scroll_repeat_count(overflow_x, scroll_sens=scroll_sens, move_sens=move_sens)
    elif overflow_x < 0 and x <= edge_margin:
        horizontal = -scroll_repeat_count(-overflow_x, scroll_sens=scroll_sens, move_sens=move_sens)

    return vertical, horizontal


def scroll_repeat_count(magnitude: int, *, scroll_sens: float, move_sens: float) -> int:
    if magnitude <= 0:
        return 0
    if move_sens <= 0:
        return 1
    return max(1, int(round(magnitude * scroll_sens / move_sens)))


def xdotool_scroll(vertical: int, horizontal: int) -> None:
    if vertical > 0:
        xdotool("click", "--repeat", str(vertical), "--delay", str(SCROLL_DELAY_MS), "5")
    elif vertical < 0:
        xdotool("click", "--repeat", str(-vertical), "--delay", str(SCROLL_DELAY_MS), "4")

    if horizontal > 0:
        xdotool("click", "--repeat", str(horizontal), "--delay", str(SCROLL_DELAY_MS), "7")
    elif horizontal < 0:
        xdotool("click", "--repeat", str(horizontal), "--delay", str(SCROLL_DELAY_MS), "6")


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
    if not dx and not dy:
        return

    screen_w, screen_h = screen_size()
    location = parse_mouse_location(run("xdotool", "getmouselocation").stdout.strip())
    if location is None:
        xdotool("mousemove_relative", "--", str(dx), str(dy))
        return

    x, y = location
    new_x, new_y, overflow_x, overflow_y = clamp_pointer_move(
        x,
        y,
        dx,
        dy,
        screen_w=screen_w,
        screen_h=screen_h,
    )
    move_x = new_x - x
    move_y = new_y - y
    if move_x or move_y:
        xdotool("mousemove_relative", "--", str(move_x), str(move_y))

    scroll_y, scroll_x = edge_scroll_clicks(
        new_x,
        new_y,
        overflow_x,
        overflow_y,
        screen_w=screen_w,
        screen_h=screen_h,
    )
    if scroll_y or scroll_x:
        xdotool_scroll(scroll_y, scroll_x)


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
    configure_from_touch_map()
    device = find_gamepad_device()
    if device is None:
        log("no gamepad device found; exiting")
        sys.exit(0)

    log(
        f"using {device} sens={SENS} deadzone={DEADZONE} "
        f"edge_margin={EDGE_MARGIN} scroll_sens={SCROLL_SENS} display={DISPLAY}"
    )
    fd = os.open(device, os.O_RDONLY)
    state = GamepadState()

    while True:
        ready, _, _ = select.select([fd], [], [], POLL_SECONDS)
        if ready:
            drain_events(fd, state)
        apply_movement(state)


if __name__ == "__main__":
    main()
