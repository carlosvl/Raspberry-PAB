#!/usr/bin/env bash
# Control panel on the MHS35 touch screen (display :1).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env"
    set +a
fi

export DISPLAY="${PAB_TOUCH_DISPLAY:-:1}"
HOST="${PAB_HOST:-127.0.0.1}"
PORT="${PAB_PORT:-8080}"
URL="${PAB_TOUCH_URL:-http://${HOST}:${PORT}/admin}"

if [[ -z "${XDG_RUNTIME_DIR:-}" && -d "/run/user/$(id -u)" ]]; then
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi

for _ in $(seq 1 60); do
    curl -sf "http://${HOST}:${PORT}/api/health" >/dev/null 2>&1 && break
    sleep 1
done

CHROMIUM=""
if [[ -x "/usr/lib/chromium/chromium" ]]; then
    CHROMIUM="/usr/lib/chromium/chromium"
else
    for candidate in chromium chromium-browser; do
        if command -v "${candidate}" >/dev/null 2>&1; then
            CHROMIUM="${candidate}"
            break
        fi
    done
fi

if [[ -z "${CHROMIUM}" ]]; then
    echo "Chromium not found" >&2
    exit 1
fi

"${SCRIPT_DIR}/keep-awake.sh" apply

command -v unclutter >/dev/null 2>&1 && unclutter -idle 0.5 -root &

PROFILE="${PAB_TOUCH_CHROMIUM_DIR:-${XDG_RUNTIME_DIR:-/tmp}/raspberry-pab-touch-chromium}"
mkdir -p "${PROFILE}"

exec "${CHROMIUM}" \
    --disable-gpu \
    --disable-gpu-rasterization \
    --kiosk \
    --start-fullscreen \
    --window-size=480,320 \
    --window-position=0,0 \
    --user-data-dir="${PROFILE}" \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-translate \
    "${URL}"
