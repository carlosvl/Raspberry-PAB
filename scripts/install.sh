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
    chromium unclutter curl \
    network-manager avahi-daemon \
    x11-xserver-utils

echo "==> Installing optional on-screen keyboard packages..."
for keyboard_package in wvkbd matchbox-keyboard onboard; do
    sudo apt-get install -y "${keyboard_package}" >/dev/null 2>&1 || true
done

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

echo "==> Allowing passwordless service restart from admin UI..."
sudo tee /etc/sudoers.d/raspberry-pab-restart >/dev/null <<EOF
${INSTALL_USER} ALL=(ALL) NOPASSWD: /bin/systemctl restart raspberry-pab
EOF
sudo chmod 440 /etc/sudoers.d/raspberry-pab-restart

echo "==> Allowing passwordless Wi-Fi management from admin UI..."
mkdir -p "${HOME}/bin"
install -m 0755 scripts/manage-pi-wifi.sh "${HOME}/bin/manage-pi-wifi.sh"
sudo tee /etc/sudoers.d/raspberry-pab-wifi >/dev/null <<EOF
${INSTALL_USER} ALL=(ALL) NOPASSWD: ${HOME}/bin/manage-pi-wifi.sh
EOF
sudo chmod 440 /etc/sudoers.d/raspberry-pab-wifi

echo "==> Allowing sleep inhibition for the kiosk service user..."
sed "s|@INSTALL_USER@|${INSTALL_USER}|g" \
    deploy/polkit/49-raspberry-pab-inhibit.rules \
    | sudo tee /etc/polkit-1/rules.d/49-raspberry-pab-inhibit.rules >/dev/null
sudo chmod 644 /etc/polkit-1/rules.d/49-raspberry-pab-inhibit.rules

echo "==> Disabling OS screen blanking..."
sudo raspi-config nonint do_blanking 1 >/dev/null 2>&1 || true

echo "==> Configuring fallback Wi-Fi hotspot..."
HOTSPOT_IFACE="${PAB_HOTSPOT_IFACE:-wlan0}"
HOTSPOT_CONNECTION="${PAB_HOTSPOT_CONNECTION:-PAB-Hotspot}"
HOTSPOT_SSID="${PAB_HOTSPOT_SSID:-Raspberry-PAB}"
HOTSPOT_PASSWORD="${PAB_HOTSPOT_PASSWORD:-RaspberryPAB123}"
if ! nmcli connection show "${HOTSPOT_CONNECTION}" >/dev/null 2>&1; then
    sudo nmcli connection add \
        type wifi \
        ifname "${HOTSPOT_IFACE}" \
        con-name "${HOTSPOT_CONNECTION}" \
        autoconnect no \
        ssid "${HOTSPOT_SSID}" \
        802-11-wireless.mode ap \
        ipv4.method shared \
        ipv6.method ignore \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "${HOTSPOT_PASSWORD}"
else
    sudo nmcli connection modify "${HOTSPOT_CONNECTION}" \
        connection.autoconnect no \
        802-11-wireless.ssid "${HOTSPOT_SSID}" \
        802-11-wireless.mode ap \
        ipv4.method shared \
        ipv6.method ignore \
        wifi-sec.key-mgmt wpa-psk \
        wifi-sec.psk "${HOTSPOT_PASSWORD}"
fi

sudo install -m 0755 deploy/network/pab-autohotspot.sh /usr/local/bin/pab-autohotspot
sed "s|/home/pi/Raspberry-PAB|${PROJECT_ROOT}|g" \
    deploy/systemd/pab-autohotspot.service \
    | sudo tee /etc/systemd/system/pab-autohotspot.service >/dev/null
sudo cp deploy/systemd/pab-autohotspot.timer /etc/systemd/system/pab-autohotspot.timer
sudo systemctl daemon-reload
sudo systemctl enable --now pab-autohotspot.timer

echo "==> Installing desktop autostart (kiosk browser)..."
AUTOSTART_DIR="${HOME}/.config/autostart"
mkdir -p "${AUTOSTART_DIR}"
sed "s|/home/pi/Raspberry-PAB|${PROJECT_ROOT}|g" \
    deploy/autostart/raspberry-pab-kiosk.desktop \
    > "${AUTOSTART_DIR}/raspberry-pab-kiosk.desktop"

echo "==> Installing desktop launcher..."
DESKTOP_DIR="${HOME}/Desktop"
if [[ -d "${DESKTOP_DIR}" ]]; then
    sed "s|/home/pi/Raspberry-PAB|${PROJECT_ROOT}|g" \
        deploy/desktop/raspberry-pab-kiosk.desktop \
        > "${DESKTOP_DIR}/raspberry-pab-kiosk.desktop"
    chmod +x "${DESKTOP_DIR}/raspberry-pab-kiosk.desktop"
    gio set "${DESKTOP_DIR}/raspberry-pab-kiosk.desktop" \
        metadata::trusted true >/dev/null 2>&1 || true
fi

chmod +x scripts/kiosk.sh scripts/touch-keyboard.sh scripts/keep-awake.sh scripts/run-server.sh

echo "==> Installing input helper scripts..."
BIN_DIR="${HOME}/bin"
mkdir -p "${BIN_DIR}"
install -m 0755 scripts/touch-trackpad.py "${BIN_DIR}/touch-trackpad.py"
install -m 0755 scripts/gamepad-mouse.py "${BIN_DIR}/gamepad-mouse.py"
install -m 0755 scripts/setup-touch-input.sh "${BIN_DIR}/setup-touch-input.sh"
install -m 0755 scripts/apply-input-config.sh "${BIN_DIR}/apply-input-config.sh"
install -m 0755 scripts/reload-kiosk-display.sh "${BIN_DIR}/reload-kiosk-display.sh"
install -m 0755 scripts/manage-pi-wifi.sh "${BIN_DIR}/manage-pi-wifi.sh"
install -m 0755 scripts/configure-pi-wifi.sh "${BIN_DIR}/configure-pi-wifi.sh"

echo ""
echo "Kiosk installation complete."
echo ""
echo "  1. Enable server:     sudo systemctl enable --now raspberry-pab"
echo "  2. Reboot or log in:  sudo reboot"
echo "  3. View server logs:  journalctl -u raspberry-pab -f"
echo "  4. Hotspot fallback:  ${HOTSPOT_SSID} (password: ${HOTSPOT_PASSWORD})"
echo ""
echo "For full kiosk setup (autologin, disable screen blanking), see docs/kiosk.md"
