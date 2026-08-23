#!/usr/bin/env bash
# Upload combined ESP32 firmware (buzzer GPIO4 + 768-LED matrix GPIO16).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FQBN="${PAB_ESP32_FQBN:-esp32:esp32:esp32}"
SKETCH="${ROOT}/hardware/esp32/raspberry_pab_hardware"
PORT="${PAB_BUZZER_PORT:-${PAB_MATRIX_PORT:-}}"
ARDUINO_CLI="${ARDUINO_CLI:-$(command -v arduino-cli || true)}"
if [[ -z "${ARDUINO_CLI}" && -x "${HOME}/.local/bin/arduino-cli" ]]; then
  ARDUINO_CLI="${HOME}/.local/bin/arduino-cli"
fi

if [[ -z "${PORT}" ]]; then
  PORT="$("${ROOT}/scripts/detect-buzzer-port.sh" 2>/dev/null || true)"
fi

if [[ -z "${PORT}" ]]; then
  echo "No ESP32 serial port found. Set PAB_BUZZER_PORT or PAB_MATRIX_PORT." >&2
  exit 1
fi

if [[ -z "${ARDUINO_CLI}" ]]; then
  echo "arduino-cli not found in PATH." >&2
  exit 1
fi

"${ARDUINO_CLI}" core update-index >/dev/null 2>&1 || true
"${ARDUINO_CLI}" core install esp32:esp32 >/dev/null 2>&1 || true
"${ARDUINO_CLI}" lib install "Adafruit NeoPixel" >/dev/null 2>&1 || true

"${ARDUINO_CLI}" compile --fqbn "${FQBN}" "${SKETCH}"
"${ARDUINO_CLI}" upload -p "${PORT}" --fqbn "${FQBN}" "${SKETCH}"
echo "Uploaded ESP32 combined hardware firmware to ${PORT}"
