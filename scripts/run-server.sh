#!/usr/bin/env bash
# Start the kiosk server with a background keep-awake refresher.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env"
    set +a
fi

"${SCRIPT_DIR}/keep-awake.sh" apply
"${SCRIPT_DIR}/keep-awake.sh" daemon &
KEEP_AWAKE_PID=$!

cleanup() {
    kill "${KEEP_AWAKE_PID}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

exec "${PROJECT_ROOT}/.venv/bin/raspberry-pab"
