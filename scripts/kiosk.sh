#!/usr/bin/env bash
# Launch Chromium in kiosk mode (run from desktop autostart on the Pi).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env"
    set +a
fi

HOST="${PAB_HOST:-127.0.0.1}"
PORT="${PAB_PORT:-8080}"
URL="${PAB_KIOSK_URL:-http://${HOST}:${PORT}}"

echo "Waiting for kiosk server at ${URL}..."
for _ in $(seq 1 60); do
    if curl -sf "${URL}/api/health" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

CHROMIUM=""
for candidate in chromium chromium-browser; do
    if command -v "${candidate}" >/dev/null 2>&1; then
        CHROMIUM="${candidate}"
        break
    fi
done

if [[ -z "${CHROMIUM}" ]]; then
    echo "Chromium not found. Install with: sudo apt install chromium" >&2
    exit 1
fi

# Hide idle cursor after 0.5s (optional, installed by install.sh)
if command -v unclutter >/dev/null 2>&1; then
    unclutter -idle 0.5 -root &
fi

exec "${CHROMIUM}" \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-translate \
    --disable-session-crashed-bubble \
    --check-for-update-interval=31536000 \
    "${URL}"
