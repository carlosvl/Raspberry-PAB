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

if [[ -z "${XDG_RUNTIME_DIR:-}" && -d "/run/user/$(id -u)" ]]; then
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi

if [[ -z "${DISPLAY:-}" && -S /tmp/.X11-unix/X0 ]]; then
    export DISPLAY=":0"
fi

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo "No desktop display found. Run this from the Pi desktop, or set DISPLAY=:0." >&2
    exit 1
fi

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

if [[ -x "/usr/lib/chromium/chromium" ]]; then
    CHROMIUM="/usr/lib/chromium/chromium"
fi

if [[ -z "${CHROMIUM}" ]]; then
    echo "Chromium not found. Install with: sudo apt install chromium" >&2
    exit 1
fi

# Hide idle cursor after 0.5s (optional, installed by install.sh)
if [[ -n "${DISPLAY:-}" ]] && command -v unclutter >/dev/null 2>&1; then
    unclutter -idle 0.5 -root &
fi

KIOSK_PROFILE_DIR="${PAB_CHROMIUM_USER_DATA_DIR:-${XDG_RUNTIME_DIR:-/tmp}/raspberry-pab-kiosk-chromium}"
mkdir -p "${KIOSK_PROFILE_DIR}"

exec "${CHROMIUM}" \
    --password-store=basic \
    --disable-gpu \
    --disable-gpu-rasterization \
    --kiosk \
    --start-fullscreen \
    --window-size=1920,1080 \
    --window-position=0,0 \
    --user-data-dir="${KIOSK_PROFILE_DIR}" \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-translate \
    --disable-session-crashed-bubble \
    --check-for-update-interval=31536000 \
    "${URL}"
