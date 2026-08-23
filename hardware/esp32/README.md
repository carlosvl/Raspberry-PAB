# ESP32 hardware (Raspberry-PAB)

Production MCU: **38-pin ESP32-WROOM** (USB-C / CP2102) with screw-terminal breakout — combined **buzzer + 3-panel WS2812 matrix**.

| Doc / sketch | Role |
|--------------|------|
| [WIRING.md](WIRING.md) | Pins, daisy-chain, power, Pi `.env` |
| [raspberry_pab_hardware/](raspberry_pab_hardware/) | Production firmware (GPIO 4 + 16, 768 LEDs) |
| [matrix_test/](matrix_test/) | Wiring smoke test |

Upload from Mac or Pi (requires `arduino-cli` + `esp32:esp32` core):

```bash
./scripts/detect-buzzer-port.sh
PAB_BUZZER_PORT=/dev/ttyUSB0 ./scripts/upload-esp32-matrix-test.sh   # wiring smoke test
PAB_BUZZER_PORT=/dev/ttyUSB0 ./scripts/upload-esp32-hardware.sh      # production
```

On macOS the port is usually `/dev/cu.usbserial-*`. On the Pi, prefer the `/dev/serial/by-id/usb-Silicon_Labs_CP2102_*` path. If the Pi has no internet, flash from the Mac and reconnect USB to the Pi.

Field power: [`../power/MOBILE-POWER.md`](../power/MOBILE-POWER.md) · Legacy Nano: [`../arduino/`](../arduino/)
