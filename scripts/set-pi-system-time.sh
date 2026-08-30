#!/usr/bin/env bash
# Set Raspberry-PAB Pi system clock (JSON-friendly for admin UI).
#
# Usage:
#   set-pi-system-time.sh status --json
#   set-pi-system-time.sh set "2026-08-29 21:38:00"
#
# When run as root (via sudo -n), privileged calls omit sudo.
# Setting time disables NTP and saves via fake-hwclock so an offline reboot
# keeps approximately the last set time (Pi has no battery RTC).

set -euo pipefail

_root() {
    if [[ "$(id -u)" -eq 0 ]]; then
        "$@"
    else
        sudo -n "$@"
    fi
}

_td() {
    _root timedatectl "$@"
}

_fake_hwclock_bin() {
    if [[ -x /sbin/fake-hwclock ]]; then
        echo /sbin/fake-hwclock
    elif [[ -x /usr/sbin/fake-hwclock ]]; then
        echo /usr/sbin/fake-hwclock
    elif command -v fake-hwclock >/dev/null 2>&1; then
        command -v fake-hwclock
    else
        return 1
    fi
}

_fake_hwclock_available() {
    _fake_hwclock_bin >/dev/null 2>&1
}

_save_persistent_clock() {
    # Persist across power loss / reboot without network (no hardware RTC).
    local bin
    if bin="$(_fake_hwclock_bin)"; then
        _root "${bin}" save >/dev/null 2>&1 || true
        return 0
    fi
    return 1
}

_status_json() {
    local local_time timezone ntp persists saved
    local_time="$(date '+%Y-%m-%dT%H:%M:%S')"
    timezone="$(timedatectl show -p Timezone --value 2>/dev/null || date '+%Z')"
    ntp="$(timedatectl show -p NTP --value 2>/dev/null || echo unknown)"
    persists=false
    saved=""
    if _fake_hwclock_available; then
        persists=true
        if [[ -f /etc/fake-hwclock.data ]]; then
            saved="$(tr -d '\n' </etc/fake-hwclock.data)"
        fi
    fi
    python3 - "$local_time" "$timezone" "$ntp" "$persists" "$saved" <<'PY'
import json, sys
print(json.dumps({
    "local_time": sys.argv[1],
    "timezone": sys.argv[2],
    "ntp": sys.argv[3].lower() in {"yes", "true", "1"},
    "ntp_raw": sys.argv[3],
    "persists_offline": sys.argv[4].lower() == "true",
    "fake_hwclock_saved": sys.argv[5] or None,
}))
PY
}

_usage() {
    echo "Usage: $0 status --json | set \"YYYY-MM-DD HH:MM:SS\"" >&2
    exit 2
}

cmd="${1:-}"
case "${cmd}" in
    status)
        if [[ "${2:-}" != "--json" ]]; then
            _usage
        fi
        _status_json
        ;;
    set)
        when="${2:-}"
        if [[ ! "${when}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}$ ]]; then
            echo "Invalid time format. Use YYYY-MM-DD HH:MM:SS" >&2
            exit 1
        fi
        # Keep NTP off across reboots so timesync cannot overwrite after boot.
        _td set-ntp false >/dev/null 2>&1 || true
        _td set-time "${when}"
        if ! _save_persistent_clock; then
            echo "Warning: fake-hwclock not installed; time may reset on reboot without network." >&2
        fi
        _status_json
        ;;
    *)
        _usage
        ;;
esac
