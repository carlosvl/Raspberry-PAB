"""Tests for gamepad device detection."""

from __future__ import annotations

from raspberry_pab.gamepad_config import find_gamepad_js_device, parse_input_devices

SAMPLE_DEVICES = """
I: Bus=0003 Vendor=0810 Product=0001 Version=0110
N: Name=" USB Gamepad          "
P: Phys=usb-0000:01:00.0-1.4/input0
H: Handlers=event5 js0 
B: PROP=0

I: Bus=001e Vendor=0000 Product=0000 Version=0000
N: Name="ADS7846 Touchscreen"
H: Handlers=event4 
B: PROP=0
"""


def test_parse_input_devices_extracts_name_and_handlers() -> None:
    devices = parse_input_devices(SAMPLE_DEVICES)
    assert len(devices) == 2
    assert devices[0]["name"] == " USB Gamepad          "
    assert "js0" in devices[0]["handlers"]


def test_find_gamepad_js_device_prefers_gamepad_name() -> None:
    assert find_gamepad_js_device(devices_text=SAMPLE_DEVICES) == "/dev/input/js0"


def test_find_gamepad_js_device_returns_none_when_missing() -> None:
    assert find_gamepad_js_device(devices_text="") is None
