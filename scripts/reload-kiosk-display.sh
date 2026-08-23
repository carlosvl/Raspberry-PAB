#!/usr/bin/env bash
# Hard-reload the HDMI kiosk Chromium window (DISPLAY :0).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export DISPLAY="${DISPLAY:-:0}"

if command -v xdotool >/dev/null 2>&1; then
    window_id="$(xdotool search --onlyvisible --class chromium 2>/dev/null | head -n 1 || true)"
    if [[ -n "${window_id}" ]]; then
        xdotool windowactivate --sync "${window_id}" key ctrl+shift+r \
            || xdotool windowactivate --sync "${window_id}" key F5
        echo "$(date -Iseconds) reload-kiosk-display: xdotool hard reload" >>/tmp/kiosk-reload.log
        exit 0
    fi
fi

pkill -f 'chromium.*raspberry-pab-kiosk' 2>/dev/null || pkill chromium 2>/dev/null || true
sleep 1
nohup "${PROJECT_ROOT}/scripts/kiosk.sh" >>/tmp/kiosk-reload.log 2>&1 &
echo "$(date -Iseconds) reload-kiosk-display: restarted kiosk.sh" >>/tmp/kiosk-reload.log
