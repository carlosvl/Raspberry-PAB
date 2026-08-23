#!/bin/bash
# Re-read touch-map.conf and restart touch trackpad + gamepad helpers (no boot delay).
# Used by admin saves (local or remote) so HDMI cursor/gamepad picks up new tuning immediately.

set -euo pipefail

CONF="${HOME}/.config/raspberry-pab/touch-map.conf"
if [[ -f "${CONF}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${CONF}"
    set +a
fi

export DISPLAY="${DISPLAY:-:0}"
MODE="${PAB_TOUCH_MAP:-mirror}"
GAMEPAD_ENABLED="${PAB_GAMEPAD_ENABLED:-1}"

if [[ "${MODE}" == "trackpad" ]] && [[ -x "${HOME}/bin/touch-trackpad.py" ]]; then
    pkill -f touch-trackpad.py 2>/dev/null || true
    nohup "${HOME}/bin/touch-trackpad.py" >>/tmp/touch-trackpad.log 2>&1 &
    echo "$(date -Iseconds) apply-input-config: restarted touch-trackpad" >>/tmp/touch-input.log
fi

pkill -f gamepad-mouse.py 2>/dev/null || true
if [[ "${GAMEPAD_ENABLED}" == "1" ]] && [[ -x "${HOME}/bin/gamepad-mouse.py" ]]; then
    nohup "${HOME}/bin/gamepad-mouse.py" >>/tmp/gamepad-mouse.log 2>&1 &
    echo "$(date -Iseconds) apply-input-config: started gamepad-mouse" >>/tmp/touch-input.log
else
    echo "$(date -Iseconds) apply-input-config: gamepad-mouse disabled" >>/tmp/touch-input.log
fi
