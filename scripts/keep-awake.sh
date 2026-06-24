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

apply_keep_awake() {
    local display

    while IFS= read -r display; do
        [[ -n "${display}" ]] || continue
        _disable_display_sleep "${display}"
    done < <(_collect_displays)

    if command -v setterm >/dev/null 2>&1; then
        setterm -blank 0 -powerdown 0 >/dev/null 2>&1 || true
    fi
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
