#!/usr/bin/env bash
# Switch wlan0 to the Raspberry-PAB hotspot only when no known Wi-Fi is connected.

set -euo pipefail

IFACE="${PAB_HOTSPOT_IFACE:-wlan0}"
HOTSPOT_CONNECTION="${PAB_HOTSPOT_CONNECTION:-PAB-Hotspot}"

if ! command -v nmcli >/dev/null 2>&1; then
    echo "NetworkManager nmcli is required for fallback hotspot mode." >&2
    exit 1
fi

DEVICE_STATE="$(nmcli -t -f DEVICE,STATE device status | awk -F: -v iface="${IFACE}" '$1 == iface { print $2 }')"
CURRENT_CONNECTION="$(nmcli -t -f GENERAL.CONNECTION device show "${IFACE}" | awk -F: '{ print $2 }')"

if [[ "${DEVICE_STATE}" == "connected" && "${CURRENT_CONNECTION}" != "${HOTSPOT_CONNECTION}" ]]; then
    nmcli connection down "${HOTSPOT_CONNECTION}" >/dev/null 2>&1 || true
    echo "${IFACE} is connected to ${CURRENT_CONNECTION}; hotspot is off."
    exit 0
fi

if [[ "${CURRENT_CONNECTION}" == "${HOTSPOT_CONNECTION}" ]]; then
    echo "${HOTSPOT_CONNECTION} is already active."
    exit 0
fi

if ! nmcli connection show "${HOTSPOT_CONNECTION}" >/dev/null 2>&1; then
    echo "Missing NetworkManager connection: ${HOTSPOT_CONNECTION}" >&2
    exit 1
fi

nmcli connection up "${HOTSPOT_CONNECTION}" ifname "${IFACE}"
echo "Started fallback hotspot ${HOTSPOT_CONNECTION} on ${IFACE}."
