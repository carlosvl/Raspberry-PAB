#!/usr/bin/env bash
# Find Arduino Nano CH340/CP210x serial port on Linux (Pi).
set -euo pipefail

if [[ -d /dev/serial/by-id ]]; then
  for link in /dev/serial/by-id/usb-*; do
    [[ -e "$link" ]] || continue
    name="$(basename "$link")"
    if [[ "$name" == *"Serial"* || "$name" == *"CP210"* || "$name" == *"FTDI"* || "$name" == *"Arduino"* ]]; then
      readlink -f "$link"
      exit 0
    fi
  done
fi

for pattern in /dev/ttyUSB* /dev/ttyACM*; do
  if [[ -e "$pattern" ]]; then
    echo "$pattern"
    exit 0
  fi
done

echo "No Arduino serial port found. Check USB cable and try: sudo modprobe ch341" >&2
exit 1
