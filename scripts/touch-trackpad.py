#!/usr/bin/env python3
"""Relative trackpad: drag on touch LCD moves HDMI cursor; tap = click."""

from __future__ import annotations

import fcntl
import glob
import os
import re
import select
import struct
import subprocess
import time

DISPLAY = os.environ.get("DISPLAY", ":0")
SENS = float(os.environ.get("PAB_TOUCH_SENS", "0.5"))
TAP_SLOP = int(os.environ.get("PAB_TOUCH_TAP_SLOP", "8"))
DRAG_START = int(os.environ.get("PAB_TOUCH_DRAG_START", "12"))
TAP_SECONDS = float(os.environ.get("PAB_TOUCH_TAP_SECONDS", "0.35"))
MULTI_TAP = os.environ.get("PAB_TOUCH_MULTI_TAP", "1") != "0"
MULTI_TAP_SECONDS = float(os.environ.get("PAB_TOUCH_MULTI_TAP_SECONDS", "0.45"))
CLICK_DELAY_MS = int(os.environ.get("PAB_TOUCH_CLICK_DELAY_MS", "80"))
DEBUG = os.environ.get("PAB_TOUCH_DEBUG", "0") == "1"
DEBUG_LOG = "/tmp/touch-trackpad.log"

EVENT_FORMAT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
POLL_SECONDS = 0.05
LOGICAL_PAD = 480
MAX_RAW_STEP = 120

EV_SYN = 0
EV_KEY = 1
EV_ABS = 3
SYN_REPORT = 0
BTN_TOUCH = 330
ABS_X = 0
ABS_Y = 1
ABS_MT_POSITION_X = 53
ABS_MT_POSITION_Y = 54

EVIOCGRAB = 0x40044590
EVIOCGABS_BASE = 0x80184540


def debug(message: str) -> None:
    if not DEBUG:
        return
    with open(DEBUG_LOG, "a", encoding="utf-8") as handle:
        handle.write(f"{time.time():.3f} {message}\n")


def find_touch_device() -> str:
    override = os.environ.get("PAB_TOUCH_DEVICE")
    if override:
        return override

    for path in sorted(glob.glob("/dev/input/event*")):
        try:
            with open(f"/sys/class/input/{os.path.basename(path)}/device/name") as f:
                if "ads7846" in f.read().lower():
                    return path
        except OSError:
            continue
    return "/dev/input/event4"


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


def pointer_location() -> tuple[int, int]:
    result = run("xdotool", "getmouselocation")
    match = re.search(r"x:(\d+)\s+y:(\d+)", result.stdout)
    if match:
        return int(match.group(1)), int(match.group(2))
    screen_w, screen_h = screen_size()
    return screen_w // 2, screen_h // 2


def screen_size() -> tuple[int, int]:
    env_w = os.environ.get("PAB_TOUCH_SCREEN_W")
    env_h = os.environ.get("PAB_TOUCH_SCREEN_H")
    if env_w and env_h:
        return int(env_w), int(env_h)

    result = run("xrandr", "--current")
    for line in result.stdout.splitlines():
        if "*" in line:
            match = re.search(r"(\d+)x(\d+)", line)
            if match:
                return int(match.group(1)), int(match.group(2))
    return 1920, 1080


def abs_max(fd: int, code: int) -> int | None:
    data = bytearray(24)
    try:
        fcntl.ioctl(fd, EVIOCGABS_BASE + code, data, True)
    except OSError:
        return None
    _value, _minimum, maximum, _fuzz, _flat, _resolution = struct.unpack("iiiiii", data)
    return int(maximum) if maximum > 0 else None


def axis_range(fd: int) -> tuple[int, int]:
    """Raw ABS axis maximum from the touch controller (e.g. ADS7846 → 4095)."""
    env_w = os.environ.get("PAB_TOUCH_RAW_MAX_X") or os.environ.get("PAB_TOUCH_PAD_W")
    env_h = os.environ.get("PAB_TOUCH_RAW_MAX_Y") or os.environ.get("PAB_TOUCH_PAD_H")
    if env_w and env_h:
        return int(env_w), int(env_h)

    width = abs_max(fd, ABS_X) or abs_max(fd, ABS_MT_POSITION_X) or 4095
    height = abs_max(fd, ABS_Y) or abs_max(fd, ABS_MT_POSITION_Y) or 4095
    return width, height


def grab_device(fd: int) -> None:
    try:
        fcntl.ioctl(fd, EVIOCGRAB, 1)
    except OSError:
        pass


def clamp(value: int, maximum: int) -> int:
    return max(0, min(maximum - 1, value))


class TrackpadState:
    def __init__(self, screen_w: int, screen_h: int, pad_w: int, pad_h: int) -> None:
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.pad_w = pad_w
        self.pad_h = pad_h
        self.scale_x = (screen_w / pad_w) * SENS
        self.scale_y = (screen_h / pad_h) * SENS
        self.tap_slop = max(TAP_SLOP, int(TAP_SLOP * pad_w / LOGICAL_PAD))
        self.drag_start = max(DRAG_START, int(DRAG_START * pad_w / LOGICAL_PAD))

        self.cx, self.cy = pointer_location()
        self.down = False
        self.moved = False
        self.touch_handled = False
        self.needs_rebase = False
        self.touch_t0 = 0.0
        self.cur_x = 0
        self.cur_y = 0
        self.origin_x = 0
        self.origin_y = 0
        self.last_x: int | None = None
        self.last_y: int | None = None
        self.max_jitter = 0

        self.tap_count = 0
        self.last_tap_end = 0.0
        self.pending_single = False
        self.pending_single_deadline = 0.0
        self.acc_x = 0.0
        self.acc_y = 0.0
        self.have_x = False
        self.have_y = False
        self.axis_src: str | None = None

    def emit_clicks(self, count: int) -> None:
        count = max(1, min(count, 3))
        if count == 1:
            xdotool("click", "1")
        else:
            xdotool("click", "--repeat", str(count), "--delay", str(CLICK_DELAY_MS), "1")
        debug(f"click count={count} at ({self.cx},{self.cy})")

    def flush_pending_single(self) -> None:
        if not self.pending_single:
            return
        if time.time() < self.pending_single_deadline:
            return
        self.emit_clicks(1)
        self.pending_single = False
        self.tap_count = 0
        debug("flush pending single click")

    def begin_touch(self) -> None:
        if self.down:
            return
        self.flush_pending_single()
        self.down = True
        self.moved = False
        self.touch_handled = False
        self.needs_rebase = True
        self.touch_t0 = time.time()
        self.last_x = None
        self.last_y = None
        self.max_jitter = 0
        self.acc_x = 0.0
        self.acc_y = 0.0
        self.have_x = False
        self.have_y = False
        self.axis_src = None
        debug(f"touch down at ({self.cx},{self.cy})")

    def end_touch(self) -> None:
        if not self.down or self.touch_handled:
            return
        self.touch_handled = True
        self.down = False
        self.needs_rebase = False
        self.last_x = None
        self.last_y = None

        if self.moved:
            self.tap_count = 0
            self.pending_single = False
            debug(f"drag end jitter={self.max_jitter}")
            return

        if (time.time() - self.touch_t0) > TAP_SECONDS:
            debug("tap too long")
            return

        now = time.time()
        if now - self.last_tap_end <= MULTI_TAP_SECONDS:
            self.tap_count += 1
        else:
            self.tap_count = 1
        self.last_tap_end = now

        if MULTI_TAP and self.tap_count >= 2:
            burst = min(self.tap_count, 3)
            self.emit_clicks(burst)
            debug(f"multi-tap burst count={burst}")
            self.tap_count = 0
            self.pending_single = False
            return

        if MULTI_TAP:
            self.pending_single = True
            self.pending_single_deadline = now + MULTI_TAP_SECONDS
            debug("pending single tap")
            return

        self.emit_clicks(1)

    def handle_syn_report(self) -> None:
        if not self.down:
            return

        if self.needs_rebase:
            if not self.have_x or not self.have_y:
                return
            self.origin_x, self.origin_y = self.cur_x, self.cur_y
            self.last_x, self.last_y = self.cur_x, self.cur_y
            self.needs_rebase = False
            return

        total_dx = self.cur_x - self.origin_x
        total_dy = self.cur_y - self.origin_y
        self.max_jitter = max(self.max_jitter, abs(total_dx), abs(total_dy))

        if not self.moved:
            if abs(total_dx) < self.tap_slop and abs(total_dy) < self.tap_slop:
                return
            if abs(total_dx) < self.drag_start and abs(total_dy) < self.drag_start:
                return
            self.moved = True
            debug(f"drag start jitter={self.max_jitter}")

        if self.last_x is None or self.last_y is None:
            self.last_x, self.last_y = self.cur_x, self.cur_y
            return

        raw_dx = self.cur_x - self.last_x
        raw_dy = self.cur_y - self.last_y
        if not self.moved and (abs(raw_dx) > MAX_RAW_STEP * 3 or abs(raw_dy) > MAX_RAW_STEP * 3):
            self.last_x, self.last_y = self.cur_x, self.cur_y
            self.origin_x, self.origin_y = self.cur_x, self.cur_y
            self.max_jitter = 0
            return

        raw_dx = max(-MAX_RAW_STEP, min(MAX_RAW_STEP, raw_dx))
        raw_dy = max(-MAX_RAW_STEP, min(MAX_RAW_STEP, raw_dy))

        self.acc_x += raw_dx * self.scale_x
        self.acc_y += raw_dy * self.scale_y
        dx = int(self.acc_x)
        dy = int(self.acc_y)
        if dx:
            self.acc_x -= dx
        if dy:
            self.acc_y -= dy

        if dx or dy:
            self.cx = clamp(self.cx + dx, self.screen_w)
            self.cy = clamp(self.cy + dy, self.screen_h)
            xdotool("mousemove", "--sync", str(self.cx), str(self.cy))

        self.last_x, self.last_y = self.cur_x, self.cur_y

    def handle_event(self, ev_type: int, code: int, value: int) -> None:
        if ev_type == EV_KEY and code == BTN_TOUCH:
            if value:
                self.begin_touch()
            else:
                self.end_touch()
            return

        if ev_type != EV_ABS:
            return

        if code == ABS_X:
            if self.axis_src is None:
                self.axis_src = "legacy"
            if self.axis_src == "legacy":
                self.cur_x = value
                self.have_x = True
        elif code == ABS_MT_POSITION_X:
            if self.axis_src is None:
                self.axis_src = "mt"
            if self.axis_src == "mt":
                self.cur_x = value
                self.have_x = True
        elif code == ABS_Y:
            if self.axis_src is None:
                self.axis_src = "legacy"
            if self.axis_src == "legacy":
                self.cur_y = value
                self.have_y = True
        elif code == ABS_MT_POSITION_Y:
            if self.axis_src is None:
                self.axis_src = "mt"
            if self.axis_src == "mt":
                self.cur_y = value
                self.have_y = True


def main() -> None:
    device = find_touch_device()
    fd = os.open(device, os.O_RDONLY)
    grab_device(fd)

    screen_w, screen_h = screen_size()
    axis_w, axis_h = axis_range(fd)
    state = TrackpadState(screen_w, screen_h, axis_w, axis_h)

    while True:
        state.flush_pending_single()
        ready, _, _ = select.select([fd], [], [], POLL_SECONDS)
        if not ready:
            continue

        data = os.read(fd, EVENT_SIZE)
        if len(data) < EVENT_SIZE:
            continue

        _sec, _usec, ev_type, code, value = struct.unpack(EVENT_FORMAT, data)
        state.handle_event(ev_type, code, value)
        if ev_type == EV_SYN and code == SYN_REPORT:
            state.handle_syn_report()


if __name__ == "__main__":
    main()
