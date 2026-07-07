"""Read and write touch-map.conf for trackpad tuning."""

from __future__ import annotations

from pathlib import Path

from raspberry_pab.gamepad_config import find_gamepad_js_device

DEFAULTS: dict[str, str] = {
    "PAB_TOUCH_MAP": "trackpad",
    "PAB_TOUCH_LCD": "guide",
    "PAB_TOUCH_SENS": "0.5",
    "PAB_TOUCH_CENTER_RESET": "1",
    "PAB_TOUCH_TAP_SLOP": "8",
    "PAB_TOUCH_DRAG_START": "12",
    "PAB_TOUCH_MULTI_TAP": "1",
    "PAB_TOUCH_MULTI_TAP_SECONDS": "0.45",
    "PAB_TOUCH_CLICK_DELAY_MS": "80",
    "PAB_GAMEPAD_ENABLED": "1",
    "PAB_GAMEPAD_SENS": "8",
    "PAB_GAMEPAD_DEADZONE": "0.15",
    "PAB_GAMEPAD_DEVICE": "auto",
    "PAB_GAMEPAD_BTN_LEFT": "1",
    "PAB_GAMEPAD_BTN_RIGHT": "2",
}

TUNABLE_KEYS = (
    "PAB_TOUCH_TAP_SLOP",
    "PAB_TOUCH_DRAG_START",
    "PAB_TOUCH_MULTI_TAP_SECONDS",
    "PAB_TOUCH_SENS",
    "PAB_GAMEPAD_ENABLED",
    "PAB_GAMEPAD_SENS",
    "PAB_GAMEPAD_DEADZONE",
)


def touch_config_path() -> Path:
    return Path.home() / ".config" / "raspberry-pab" / "touch-map.conf"


def load_touch_config(path: Path | None = None) -> dict[str, str]:
    config_path = path or touch_config_path()
    values = dict(DEFAULTS)
    if not config_path.is_file():
        return values

    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def save_touch_config(updates: dict[str, str], path: Path | None = None) -> dict[str, str]:
    config_path = path or touch_config_path()
    current = load_touch_config(config_path)
    current.update(updates)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Touch input + LCD options for Raspberry-PAB kiosk",
        "# Managed via Admin -> Touch",
        "",
        f"PAB_TOUCH_MAP={current['PAB_TOUCH_MAP']}",
        f"PAB_TOUCH_LCD={current['PAB_TOUCH_LCD']}",
        "",
        f"PAB_TOUCH_SENS={current['PAB_TOUCH_SENS']}",
        f"PAB_TOUCH_CENTER_RESET={current.get('PAB_TOUCH_CENTER_RESET', '1')}",
        f"PAB_TOUCH_TAP_SLOP={current['PAB_TOUCH_TAP_SLOP']}",
        f"PAB_TOUCH_DRAG_START={current['PAB_TOUCH_DRAG_START']}",
        f"PAB_TOUCH_MULTI_TAP={current.get('PAB_TOUCH_MULTI_TAP', '1')}",
        f"PAB_TOUCH_MULTI_TAP_SECONDS={current['PAB_TOUCH_MULTI_TAP_SECONDS']}",
        f"PAB_TOUCH_CLICK_DELAY_MS={current.get('PAB_TOUCH_CLICK_DELAY_MS', '80')}",
        "",
        f"PAB_GAMEPAD_ENABLED={current.get('PAB_GAMEPAD_ENABLED', '1')}",
        f"PAB_GAMEPAD_SENS={current.get('PAB_GAMEPAD_SENS', '8')}",
        f"PAB_GAMEPAD_DEADZONE={current.get('PAB_GAMEPAD_DEADZONE', '0.15')}",
        f"PAB_GAMEPAD_DEVICE={current.get('PAB_GAMEPAD_DEVICE', 'auto')}",
        f"PAB_GAMEPAD_BTN_LEFT={current.get('PAB_GAMEPAD_BTN_LEFT', '1')}",
        f"PAB_GAMEPAD_BTN_RIGHT={current.get('PAB_GAMEPAD_BTN_RIGHT', '2')}",
        "",
    ]
    config_path.write_text("\n".join(lines), encoding="utf-8")
    return current


def touch_response(path: Path | None = None) -> dict[str, str | float | int | bool | None]:
    values = load_touch_config(path)
    detected = find_gamepad_js_device()
    return {
        "touch_map": values.get("PAB_TOUCH_MAP", "trackpad"),
        "touch_lcd": values.get("PAB_TOUCH_LCD", "guide"),
        "tap_slop": int(values.get("PAB_TOUCH_TAP_SLOP", "8")),
        "drag_start": int(values.get("PAB_TOUCH_DRAG_START", "12")),
        "multi_tap_seconds": float(values.get("PAB_TOUCH_MULTI_TAP_SECONDS", "0.45")),
        "sensitivity": float(values.get("PAB_TOUCH_SENS", "0.5")),
        "gamepad_enabled": values.get("PAB_GAMEPAD_ENABLED", "1") == "1",
        "gamepad_sensitivity": float(values.get("PAB_GAMEPAD_SENS", "8")),
        "gamepad_deadzone": float(values.get("PAB_GAMEPAD_DEADZONE", "0.15")),
        "gamepad_device": detected,
    }
