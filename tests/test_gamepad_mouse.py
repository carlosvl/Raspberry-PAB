"""Tests for gamepad mouse edge-scroll helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gamepad-mouse.py"
_spec = importlib.util.spec_from_file_location("gamepad_mouse_script", _SCRIPT)
assert _spec and _spec.loader
gamepad_mouse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gamepad_mouse)


def test_clamp_pointer_move_stops_at_bottom_edge() -> None:
    new_x, new_y, overflow_x, overflow_y = gamepad_mouse.clamp_pointer_move(
        100,
        1079,
        0,
        20,
        screen_w=1920,
        screen_h=1080,
    )
    assert new_y == 1079
    assert overflow_y == 20
    assert overflow_x == 0
    assert new_x == 100


def test_edge_scroll_clicks_when_pushing_past_bottom() -> None:
    vertical, horizontal = gamepad_mouse.edge_scroll_clicks(
        960,
        1079,
        0,
        8,
        screen_w=1920,
        screen_h=1080,
        edge_margin=16,
        scroll_sens=0.35,
        move_sens=8,
    )
    assert vertical == 1
    assert horizontal == 0


def test_edge_scroll_clicks_when_pushing_past_top() -> None:
    vertical, horizontal = gamepad_mouse.edge_scroll_clicks(
        960,
        0,
        0,
        -8,
        screen_w=1920,
        screen_h=1080,
        edge_margin=16,
        scroll_sens=0.35,
        move_sens=8,
    )
    assert vertical == -1
    assert horizontal == 0


def test_no_edge_scroll_when_cursor_not_at_edge() -> None:
    vertical, horizontal = gamepad_mouse.edge_scroll_clicks(
        960,
        540,
        0,
        8,
        screen_w=1920,
        screen_h=1080,
    )
    assert vertical == 0
    assert horizontal == 0


def test_parse_mouse_location() -> None:
    assert gamepad_mouse.parse_mouse_location("x:353 y:80 screen:0 window:123") == (353, 80)


def test_configure_from_touch_map_reads_saved_speed(tmp_path) -> None:
    conf = tmp_path / "touch-map.conf"
    conf.write_text("PAB_GAMEPAD_SENS=14\nPAB_GAMEPAD_DEADZONE=0.2\n", encoding="utf-8")
    gamepad_mouse.configure_from_touch_map(gamepad_mouse.read_touch_map_conf(str(conf)))
    assert gamepad_mouse.SENS == 14.0
    assert gamepad_mouse.DEADZONE == 0.2
