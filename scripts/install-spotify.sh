#!/usr/bin/env bash
# Install go-librespot as a Spotify Connect receiver ("PAB Board") for the kiosk user.
# Plays through PipeWire's Pulse layer, so it follows the same Bluetooth/HDMI sink
# as alerts. The local control API listens on 127.0.0.1:3678 only.
# Usage: ./scripts/install-spotify.sh [--version vX.Y.Z] [--force-config]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
GO_LIBRESPOT_VERSION="v0.10.2"
FORCE_CONFIG=false
BIN_PATH="/usr/local/bin/go-librespot"
CONFIG_DIR="${HOME}/.config/go-librespot"
UNIT_DIR="${HOME}/.config/systemd/user"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --version) GO_LIBRESPOT_VERSION="$2"; shift 2 ;;
        --force-config) FORCE_CONFIG=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

case "$(uname -m)" in
    aarch64|arm64) ASSET="go-librespot_linux_arm64.tar.gz" ;;
    armv6l|armv7l) ASSET="go-librespot_linux_armv6_rpi.tar.gz" ;;
    x86_64) ASSET="go-librespot_linux_x86_64.tar.gz" ;;
    *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

URL="https://github.com/devgianlu/go-librespot/releases/download/${GO_LIBRESPOT_VERSION}/${ASSET}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

echo "==> Downloading go-librespot ${GO_LIBRESPOT_VERSION} (${ASSET})..."
curl -fsSL "${URL}" -o "${TMP_DIR}/${ASSET}"
tar -xzf "${TMP_DIR}/${ASSET}" -C "${TMP_DIR}"
sudo install -m 0755 "${TMP_DIR}/go-librespot" "${BIN_PATH}"

mkdir -p "${CONFIG_DIR}"
if [[ ! -f "${CONFIG_DIR}/config.yml" || "${FORCE_CONFIG}" == true ]]; then
    echo "==> Writing ${CONFIG_DIR}/config.yml..."
    cat > "${CONFIG_DIR}/config.yml" <<'YAML'
log_level: info
device_name: PAB Board
device_type: speaker
# PipeWire's Pulse layer: same Bluetooth/HDMI sink as alerts.
audio_backend: pulseaudio
volume_steps: 100
initial_volume: 60
# Log in once with a code at spotify.com/pair; credentials persist in state.json.
credentials:
  type: device_auth
# Still show up as a speaker in the Spotify app on the same Wi-Fi.
zeroconf_enabled: true
server:
  enabled: true
  address: 127.0.0.1
  port: 3678
YAML
else
    echo "==> Keeping existing ${CONFIG_DIR}/config.yml (use --force-config to overwrite)"
fi

echo "==> Installing user service pab-spotify..."
mkdir -p "${UNIT_DIR}"
install -m 0644 "${PROJECT_ROOT}/deploy/systemd/pab-spotify.service" \
    "${UNIT_DIR}/pab-spotify.service"
systemctl --user daemon-reload
systemctl --user enable --now pab-spotify.service

cat <<'EOF'

==> go-librespot installed.
First-time login (once):
  1. journalctl --user -u pab-spotify -f   (or: curl -s 127.0.0.1:3678/auth/code)
  2. Open spotify.com/pair on your phone and enter the code shown.
Check:  curl -s 127.0.0.1:3678/status
EOF
