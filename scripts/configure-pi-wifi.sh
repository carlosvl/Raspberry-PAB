#!/usr/bin/env bash
# Configure Raspberry-PAB Pi Wi-Fi via NetworkManager.
# Run ON the Pi (SSH or local terminal).
#
# Thin CLI wrapper around manage-pi-wifi.sh.
#
# Brings down the PAB fallback hotspot first — wlan0 cannot scan while acting as AP.
# Restores the hotspot if scan/connect fails so you don't lose SSH access.
#
# Usage:
#   ./scripts/configure-pi-wifi.sh "SSID" "password"
#   ./scripts/configure-pi-wifi.sh "SSID"              # open network (no password)
#   ./scripts/configure-pi-wifi.sh --list              # scan only, then restore hotspot
#
# Example:
#   ./scripts/configure-pi-wifi.sh "QualitySuites" "your-wifi-password"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANAGE="${SCRIPT_DIR}/manage-pi-wifi.sh"

if [[ ! -x "${MANAGE}" ]]; then
    echo "Missing manage-pi-wifi.sh at ${MANAGE}" >&2
    exit 1
fi

if [[ "${1:-}" == "--list" ]]; then
    echo "==> Scanning nearby networks..."
    "${MANAGE}" scan
    exit 0
fi

SSID="${1:-}"
PASSWORD="${2:-}"

if [[ -z "${SSID}" ]]; then
    echo "Usage: $(basename "$0") \"SSID\" [password]" >&2
    echo "       $(basename "$0") --list" >&2
    exit 1
fi

echo "==> Connecting to ${SSID}..."
if [[ -n "${PASSWORD}" ]]; then
    "${MANAGE}" connect "${SSID}" "${PASSWORD}"
else
    "${MANAGE}" connect "${SSID}"
fi

echo ""
echo "Done. Your SSH session may drop when the hotspot stops."
echo "Reconnect your Mac to the same Wi-Fi, then: ssh carlos@<pi-ip>"
