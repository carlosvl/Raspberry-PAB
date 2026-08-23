#!/usr/bin/env bash
# Configure Raspberry-PAB Pi Wi-Fi via NetworkManager.
# Run ON the Pi (SSH or local terminal).
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

HOTSPOT_CONNECTION="${PAB_HOTSPOT_CONNECTION:-PAB-Hotspot}"
IFACE="${PAB_HOTSPOT_IFACE:-wlan0}"
HOTSPOT_WAS_ACTIVE=0

if ! command -v nmcli >/dev/null 2>&1; then
    echo "nmcli (NetworkManager) is required." >&2
    exit 1
fi

_current_connection() {
    nmcli -t -f GENERAL.CONNECTION device show "${IFACE}" 2>/dev/null | awk -F: '{ print $2 }' | tr -d ' '
}

_stop_hotspot_for_scan() {
    if [[ "$(_current_connection)" == "${HOTSPOT_CONNECTION}" ]]; then
        HOTSPOT_WAS_ACTIVE=1
    fi
    echo "==> Stopping fallback hotspot (wlan0 must be in client mode to scan)..."
    sudo systemctl stop pab-autohotspot.timer 2>/dev/null || true
    sudo nmcli connection down "${HOTSPOT_CONNECTION}" >/dev/null 2>&1 || true
    sudo nmcli radio wifi on >/dev/null 2>&1 || true
    sleep 2
}

_restore_hotspot() {
    if [[ "${HOTSPOT_WAS_ACTIVE}" != "1" ]]; then
        return 0
    fi
    echo "==> Restoring fallback hotspot ${HOTSPOT_CONNECTION}..."
    sudo nmcli connection up "${HOTSPOT_CONNECTION}" ifname "${IFACE}" >/dev/null 2>&1 \
        || /usr/local/bin/pab-autohotspot 2>/dev/null \
        || true
    sudo systemctl start pab-autohotspot.timer 2>/dev/null || true
    echo "Hotspot should be back in ~10s. Reconnect Mac to ${PAB_HOTSPOT_SSID:-Raspberry-PAB}, then ssh carlos@10.42.0.1"
}

_scan_wifi() {
    echo "==> Scanning nearby networks on ${IFACE}..."
    sudo nmcli device wifi rescan ifname "${IFACE}" >/dev/null 2>&1 \
        || nmcli device wifi rescan >/dev/null 2>&1 \
        || true
    sleep 3
    nmcli -f IN-USE,SSID,SIGNAL,SECURITY device wifi list ifname "${IFACE}" 2>/dev/null \
        || nmcli -f IN-USE,SSID,SIGNAL,SECURITY device wifi list
}

if [[ "${1:-}" == "--list" ]]; then
    _stop_hotspot_for_scan
    _scan_wifi
    _restore_hotspot
    exit 0
fi

SSID="${1:-}"
PASSWORD="${2:-}"

if [[ -z "${SSID}" ]]; then
    echo "Usage: $(basename "$0") \"SSID\" [password]" >&2
    echo "       $(basename "$0") --list" >&2
    exit 1
fi

_stop_hotspot_for_scan
_scan_wifi

if ! nmcli -t -f SSID device wifi list ifname "${IFACE}" 2>/dev/null | grep -Fxq "${SSID}"; then
    if ! nmcli -t -f SSID device wifi list | grep -Fxq "${SSID}"; then
        echo "Warning: ${SSID} not in scan results — check exact spelling/caps above." >&2
    fi
fi

echo "==> Connecting to ${SSID}..."
set +e
if [[ -n "${PASSWORD}" ]]; then
    CONNECT_OUT="$(sudo nmcli device wifi connect "${SSID}" password "${PASSWORD}" ifname "${IFACE}" 2>&1)"
    CONNECT_RC=$?
else
    CONNECT_OUT="$(sudo nmcli device wifi connect "${SSID}" ifname "${IFACE}" 2>&1)"
    CONNECT_RC=$?
fi
set -e

if [[ "${CONNECT_RC}" != "0" ]]; then
    echo "${CONNECT_OUT}" >&2
    echo "Connection failed." >&2
    _restore_hotspot
    exit 1
fi

echo "${CONNECT_OUT}"
sudo systemctl start pab-autohotspot.timer 2>/dev/null || true

echo "==> Active connection:"
nmcli -t -f NAME,TYPE,DEVICE connection show --active

echo "==> Pi address on ${IFACE}:"
ip -4 -o addr show "${IFACE}" 2>/dev/null | awk '{print $4}' || true

echo ""
echo "Done. Your SSH session may drop when the hotspot stops."
echo "Reconnect your Mac to ${SSID}, then: ssh carlos@<pi-ip-above>"
