#!/usr/bin/env bash
# Launch an installed on-screen keyboard for the Raspberry Pi touchscreen.

set -euo pipefail

if [[ -z "${XDG_RUNTIME_DIR:-}" && -d "/run/user/$(id -u)" ]]; then
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi

if [[ -z "${WAYLAND_DISPLAY:-}" && -n "${XDG_RUNTIME_DIR:-}" && -S "${XDG_RUNTIME_DIR}/wayland-0" ]]; then
    export WAYLAND_DISPLAY="wayland-0"
fi

if [[ -z "${DISPLAY:-}" && -S /tmp/.X11-unix/X0 ]]; then
    export DISPLAY=":0"
fi

launch_keyboard() {
    local command_name="$1"
    shift
    if command -v "${command_name}" >/dev/null 2>&1; then
        "${command_name}" "$@" >/dev/null 2>&1 &
        echo "Started ${command_name}."
        return 0
    fi
    return 1
}

if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    if launch_keyboard wvkbd-mobintl || launch_keyboard wvkbd; then
        exit 0
    fi
fi

if [[ -n "${DISPLAY:-}" ]]; then
    if launch_keyboard matchbox-keyboard || launch_keyboard onboard; then
        exit 0
    fi
fi

echo "No supported on-screen keyboard found. Install wvkbd, matchbox-keyboard, or onboard." >&2
exit 1
