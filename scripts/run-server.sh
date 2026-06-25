#!/usr/bin/env bash
# Start the kiosk server with a background keep-awake refresher.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVER_BIN="${PROJECT_ROOT}/.venv/bin/raspberry-pab"

if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env"
    set +a
fi

_start_touch_input() {
    local script="${HOME}/bin/setup-touch-input.sh"
    if [[ -f "${script}" ]]; then
        DISPLAY="${DISPLAY:-:0}" bash "${script}" >/dev/null 2>&1 &
    fi
}

_start_touch_input
"${SCRIPT_DIR}/keep-awake.sh" apply
"${SCRIPT_DIR}/keep-awake.sh" daemon &
KEEP_AWAKE_PID=$!

cleanup() {
    kill "${KEEP_AWAKE_PID}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

if command -v systemd-inhibit >/dev/null 2>&1; then
    if systemd-inhibit \
        --what=idle:sleep:handle-lid-switch:handle-suspend-key:handle-hibernate-key \
        --who=Raspberry-PAB \
        --why="Schedule kiosk must stay online" \
        --mode=block \
        "${SERVER_BIN}"; then
        exit 0
    fi
fi

exec "${SERVER_BIN}"
