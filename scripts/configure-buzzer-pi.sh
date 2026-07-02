#!/usr/bin/env bash
# Detect Nano port, update .env, upload firmware, restart kiosk service.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"

sudo modprobe ch341 2>/dev/null || true
sudo modprobe cp210x 2>/dev/null || true

PORT="$("${ROOT}/scripts/detect-buzzer-port.sh")"
ARDUINO_CLI="${HOME}/.local/bin/arduino-cli"

if [[ ! -x "${ARDUINO_CLI}" ]]; then
  echo "arduino-cli not found at ${ARDUINO_CLI}" >&2
  exit 1
fi

touch "${ENV_FILE}"
if grep -q '^PAB_BUZZER_PORT=' "${ENV_FILE}"; then
  sed -i "s|^PAB_BUZZER_PORT=.*|PAB_BUZZER_PORT=${PORT}|" "${ENV_FILE}"
else
  echo "PAB_BUZZER_PORT=${PORT}" >> "${ENV_FILE}"
fi

if ! grep -q '^PAB_BUZZER_ENABLED=' "${ENV_FILE}"; then
  echo "PAB_BUZZER_ENABLED=true" >> "${ENV_FILE}"
fi
if ! grep -q '^PAB_BUZZER_MODE=' "${ENV_FILE}"; then
  echo "PAB_BUZZER_MODE=active" >> "${ENV_FILE}"
fi
if ! grep -q '^PAB_BUZZER_BAUD=' "${ENV_FILE}"; then
  echo "PAB_BUZZER_BAUD=115200" >> "${ENV_FILE}"
fi

export PAB_BUZZER_PORT="${PORT}"
"${ROOT}/scripts/upload-buzzer.sh"

sudo systemctl restart raspberry-pab
echo "Buzzer configured on ${PORT}"
