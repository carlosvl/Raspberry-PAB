#!/bin/bash
# Configure MHS35 touch -> HDMI pointer mapping and optional gamepad mouse.
# Modes (set PAB_TOUCH_MAP in ~/.config/raspberry-pab/touch-map.conf):
#   mirror  - full-screen map (default, use with fb-mirror on touch LCD)
#   corner  - top-right 480x320 only (admin hotspot zone on HDMI)
#   trackpad - relative movement like a mouse pad

set -euo pipefail

CONF="${HOME}/.config/raspberry-pab/touch-map.conf"
[[ -f "${CONF}" ]] && source "${CONF}"
MODE="${PAB_TOUCH_MAP:-mirror}"
GAMEPAD_ENABLED="${PAB_GAMEPAD_ENABLED:-1}"

sleep 6
export DISPLAY=:0

TOUCH_ID=$(xinput list | awk 'tolower($0) ~ /ads7846/ {
    for (i = 1; i <= NF; i++) {
        if ($i ~ /^id=/) {
            sub(/^id=/, "", $i)
            print $i
            exit
        }
    }
}')
if [[ -n "${TOUCH_ID}" ]]; then
    xinput map-to-output "${TOUCH_ID}" HDMI-1 2>/dev/null || true

    case "${MODE}" in
        mirror)
            xinput enable "${TOUCH_ID}" 2>/dev/null || true
            xinput set-prop "${TOUCH_ID}" --type=float "Coordinate Transformation Matrix" \
                4 0 0  0 3.375 0  0 0 1
            ;;
        corner)
            xinput enable "${TOUCH_ID}" 2>/dev/null || true
            xinput set-prop "${TOUCH_ID}" --type=float "Coordinate Transformation Matrix" \
                0.25 0 0.75  0 0.296 0  0 0 1
            ;;
        trackpad)
            xinput set-prop "${TOUCH_ID}" --type=float "Coordinate Transformation Matrix" \
                1 0 0  0 1 0  0 0 1
            xinput disable "${TOUCH_ID}" 2>/dev/null || true
            if [[ -x "${HOME}/bin/touch-trackpad.py" ]]; then
                pkill -f touch-trackpad.py 2>/dev/null || true
                nohup "${HOME}/bin/touch-trackpad.py" >>/tmp/touch-trackpad.log 2>&1 &
            fi
            ;;
        *)
            echo "Unknown PAB_TOUCH_MAP=${MODE}" >&2
            ;;
    esac
else
    echo "No touch device" >&2
fi

pkill -f gamepad-mouse.py 2>/dev/null || true
if [[ "${GAMEPAD_ENABLED}" == "1" ]] && [[ -x "${HOME}/bin/gamepad-mouse.py" ]]; then
    nohup "${HOME}/bin/gamepad-mouse.py" >>/tmp/gamepad-mouse.log 2>&1 &
    echo "Gamepad mouse: started" >>/tmp/touch-input.log
else
    echo "Gamepad mouse: disabled" >>/tmp/touch-input.log
fi

echo "Touch map: ${MODE}" >>/tmp/touch-input.log
