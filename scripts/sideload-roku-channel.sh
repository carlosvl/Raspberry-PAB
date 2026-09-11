#!/usr/bin/env bash
# Package and sideload the Raspberry-PAB Roku channel (developer mode).
#
# Usage:
#   ./scripts/sideload-roku-channel.sh <roku-ip> [developer-password]
#
# Prerequisites on the Roku (once at home):
#   Settings → System → Advanced system settings → Developer options
#   Enable installer, set a password, note the IP shown.
#
# Env overrides:
#   ROKU_IP, ROKU_PASSWORD, ROKU_CHANNEL_DIR

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CHANNEL_DIR="${ROKU_CHANNEL_DIR:-${PROJECT_ROOT}/roku/pab-channel}"
ROKU_IP="${1:-${ROKU_IP:-}}"
ROKU_PASSWORD="${2:-${ROKU_PASSWORD:-}}"

if [[ -z "${ROKU_IP}" ]]; then
    echo "Usage: $0 <roku-ip> [developer-password]" >&2
    exit 1
fi

if [[ -z "${ROKU_PASSWORD}" ]]; then
    read -r -s -p "Roku developer password: " ROKU_PASSWORD
    echo
fi

if [[ ! -d "${CHANNEL_DIR}" ]]; then
    echo "Channel directory not found: ${CHANNEL_DIR}" >&2
    exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT
ZIP_PATH="${TMP_DIR}/pab-channel.zip"

echo "==> Packaging ${CHANNEL_DIR}"
(
    cd "${CHANNEL_DIR}"
    # Roku expects archive contents at the zip root (manifest at top level).
    zip -r -q "${ZIP_PATH}" . -x "*.DS_Store" -x "*/.git/*"
)

echo "==> Removing previous sideloaded channel (if any)"
curl -sS -u "rokudev:${ROKU_PASSWORD}" \
    --digest \
    -F "mysubmit=Delete" \
    -F "archive=" \
    "http://${ROKU_IP}/plugin_install" >/dev/null || true

echo "==> Installing package to ${ROKU_IP}"
RESPONSE="$(
    curl -sS -u "rokudev:${ROKU_PASSWORD}" \
        --digest \
        -F "mysubmit=Install" \
        -F "archive=@${ZIP_PATH}" \
        "http://${ROKU_IP}/plugin_install"
)"

if echo "${RESPONSE}" | grep -qiE "Failed|Incorrect|error"; then
    echo "${RESPONSE}" >&2
    echo "Sideload may have failed — check developer password and that installer is enabled." >&2
    exit 1
fi

echo "==> Done. Launch with:"
echo "    curl -d '' \"http://${ROKU_IP}:8060/launch/dev?contentId=http%3A%2F%2F<pi-ip>%3A8080\""
echo "Or use Admin → TVs → Show board on the Pi."
