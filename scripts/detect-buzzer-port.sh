#!/usr/bin/env bash
# Find ESP32 (CP2102) or Arduino Nano (CH340/CP210x) serial port on Linux/macOS.
set -euo pipefail

if [[ -d /dev/serial/by-id ]]; then
  for link in /dev/serial/by-id/usb-*; do
    [[ -e "$link" ]] || continue
    name="$(basename "$link")"
    # Prefer CP2102 / Silicon Labs (ESP32 DevKit USB-C) when present.
    if [[ "$name" == *"CP210"* || "$name" == *"Silicon_Labs"* || "$name" == *"SLAB"* ]]; then
      readlink -f "$link"
      exit 0
    fi
  done
  for link in /dev/serial/by-id/usb-*; do
    [[ -e "$link" ]] || continue
    name="$(basename "$link")"
    if [[ "$name" == *"Serial"* || "$name" == *"FTDI"* || "$name" == *"Arduino"* || "$name" == *"1a86"* ]]; then
      readlink -f "$link"
      exit 0
    fi
  done
fi

# macOS ESP32 / CP2102
for pattern in /dev/cu.SLAB_USBtoUART* /dev/cu.usbserial* /dev/cu.wchusbserial*; do
  if [[ -e "$pattern" ]]; then
    echo "$pattern"
    exit 0
  fi
done

for pattern in /dev/ttyUSB* /dev/ttyACM*; do
  if [[ -e "$pattern" ]]; then
    echo "$pattern"
    exit 0
  fi
done

echo "No ESP32/Arduino serial port found. Check USB cable (CP2102 or CH340)." >&2
exit 1
