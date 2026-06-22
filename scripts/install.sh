#!/usr/bin/env bash
# Install Raspberry-PAB kiosk on Raspberry Pi OS (Bookworm+).
# Usage: ./scripts/install.sh [--dev]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INSTALL_DEV=false
INSTALL_USER="$(id -un)"
INSTALL_GROUP="$(id -gn)"

for arg in "$@"; do
    case "$arg" in
        --dev) INSTALL_DEV=true ;;
        *) echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done

echo "==> Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3 python3-venv python3-pip git \
    chromium unclutter curl

cd "${PROJECT_ROOT}"

echo "==> Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

if [[ "${INSTALL_DEV}" == true ]]; then
    echo "==> Installing package with dev dependencies..."
    pip install -e ".[dev]"
else
    echo "==> Installing package..."
    pip install .
fi

echo "==> Installing systemd service..."
sed \
    -e "s|User=pi|User=${INSTALL_USER}|g" \
    -e "s|Group=pi|Group=${INSTALL_GROUP}|g" \
    -e "s|/home/pi/Raspberry-PAB|${PROJECT_ROOT}|g" \
    deploy/systemd/raspberry-pab.service \
    | sudo tee /etc/systemd/system/raspberry-pab.service >/dev/null
sudo systemctl daemon-reload

echo "==> Installing desktop autostart (kiosk browser)..."
AUTOSTART_DIR="${HOME}/.config/autostart"
mkdir -p "${AUTOSTART_DIR}"
sed "s|/home/pi/Raspberry-PAB|${PROJECT_ROOT}|g" \
    deploy/autostart/raspberry-pab-kiosk.desktop \
    > "${AUTOSTART_DIR}/raspberry-pab-kiosk.desktop"

chmod +x scripts/kiosk.sh

echo ""
echo "Kiosk installation complete."
echo ""
echo "  1. Enable server:     sudo systemctl enable --now raspberry-pab"
echo "  2. Reboot or log in:  sudo reboot"
echo "  3. View server logs:  journalctl -u raspberry-pab -f"
echo ""
echo "For full kiosk setup (autologin, disable screen blanking), see docs/kiosk.md"
