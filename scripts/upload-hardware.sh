#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FQBN="${PAB_BUZZER_FQBN:-arduino:avr:nano:cpu=atmega328old}"
SKETCH="${ROOT}/hardware/arduino/raspberry_pab_hardware"
PORT="${PAB_BUZZER_PORT:-${PAB_MATRIX_PORT:-}}"
ARDUINO_CLI="${ARDUINO_CLI:-$(command -v arduino-cli || true)}"
if [[ -z "${ARDUINO_CLI}" && -x "${HOME}/.local/bin/arduino-cli" ]]; then
  ARDUINO_CLI="${HOME}/.local/bin/arduino-cli"
fi

if [[ -z "${PORT}" ]]; then
  PORT="$("${ROOT}/scripts/detect-buzzer-port.sh" 2>/dev/null || true)"
fi

if [[ -z "${PORT}" ]]; then
  echo "No Arduino serial port found. Set PAB_BUZZER_PORT or PAB_MATRIX_PORT." >&2
  exit 1
fi

if [[ -z "${ARDUINO_CLI}" ]]; then
  echo "arduino-cli not found in PATH." >&2
  exit 1
fi

"${ARDUINO_CLI}" lib install "Adafruit NeoPixel" >/dev/null 2>&1 || true

# Keep default 64-byte RX buffer — Nano SRAM is tight with 512 LEDs (1536-byte pixel buffer).
# Pi truncates scroll text to 80 chars; keep SCROLL lines under ~100 bytes.
"${ARDUINO_CLI}" compile --fqbn "${FQBN}" "${SKETCH}"
"${ARDUINO_CLI}" upload -p "${PORT}" --fqbn "${FQBN}" "${SKETCH}"
echo "Uploaded combined hardware firmware to ${PORT}"
