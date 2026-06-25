#!/usr/bin/env bash
# Keep the Pi awake while Raspberry-PAB is running (display + idle sleep).

set -euo pipefail

REFRESH_SECONDS="${PAB_KEEP_AWAKE_INTERVAL:-45}"

_collect_displays() {
    local displays=()
    local display

    if [[ -n "${DISPLAY:-}" ]]; then
        displays+=("${DISPLAY}")
    fi
    if [[ -n "${PAB_TOUCH_DISPLAY:-}" ]]; then
        displays+=("${PAB_TOUCH_DISPLAY}")
    fi

    for display in :0 :1; do
        if [[ -S "/tmp/.X11-unix/X${display#:}" ]]; then
            displays+=("${display}")
        fi
    done

    if ((${#displays[@]} == 0)); then
        return 0
    fi

    printf '%s\n' "${displays[@]}" | awk '!seen[$0]++'
}

_disable_display_sleep() {
    local display="$1"
    if ! command -v xset >/dev/null 2>&1; then
        return 0
    fi

    DISPLAY="${display}" xset s off >/dev/null 2>&1 || true
    DISPLAY="${display}" xset -dpms >/dev/null 2>&1 || true
    DISPLAY="${display}" xset s noblank >/dev/null 2>&1 || true
}

_ensure_touch_trackpad() {
    local conf="${HOME}/.config/raspberry-pab/touch-map.conf"
    [[ -f "${conf}" ]] || return 0

    # shellcheck disable=SC1090
    source "${conf}"
    [[ "${PAB_TOUCH_MAP:-mirror}" == "trackpad" ]] || return 0
    pgrep -f 'touch-trackpad.py' >/dev/null 2>&1 && return 0

    local script="${HOME}/bin/touch-trackpad.py"
    [[ -x "${script}" ]] || return 0

    pkill -f 'touch-trackpad.py' 2>/dev/null || true
    export DISPLAY="${DISPLAY:-:0}"
    nohup "${script}" >>/tmp/touch-trackpad.log 2>&1 &
    echo "$(date -Iseconds) restarted touch-trackpad (was missing)" >>/tmp/touch-watchdog.log
}

apply_keep_awake() {
    local display

    while IFS= read -r display; do
        [[ -n "${display}" ]] || continue
        _disable_display_sleep "${display}"
    done < <(_collect_displays)

    if command -v setterm >/dev/null 2>&1; then
        setterm -blank 0 -powerdown 0 >/dev/null 2>&1 || true
    fi

    _ensure_touch_trackpad
}

daemon_keep_awake() {
    while true; do
        apply_keep_awake
        sleep "${REFRESH_SECONDS}"
    done
}

usage() {
    echo "Usage: $(basename "$0") [apply|daemon]" >&2
}

case "${1:-apply}" in
    apply)
        apply_keep_awake
        ;;
    daemon)
        daemon_keep_awake
        ;;
    *)
        usage
        exit 1
        ;;
esac
