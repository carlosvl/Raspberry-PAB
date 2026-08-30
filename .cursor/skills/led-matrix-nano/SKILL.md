---
name: led-matrix-esp32
description: >-
  Extend or debug the Raspberry-PAB triple 8×32 WS2812 matrix driven by ESP32
  over USB serial (combined buzzer + matrix). Use when changing ESP32 firmware,
  serial protocol, matrix_controller, admin Test matrix, upload-esp32 scripts,
  3-panel wiring, or legacy Nano 2-panel SRAM issues.
---

# LED matrix (ESP32 + triple 8×32 WS2812)

## Architecture

| Piece | Path / role |
|-------|-------------|
| **Production firmware** | `hardware/esp32/raspberry_pab_hardware/` — buzzer GPIO **4** + matrix DIN GPIO **16**, **768** LEDs |
| Wiring smoke test | `hardware/esp32/matrix_test/` — wipe/rainbow across three panels |
| Upload | `scripts/upload-esp32-hardware.sh`, `scripts/upload-esp32-matrix-test.sh` |
| Serial helpers | `src/raspberry_pab/arduino_serial.py` (shared with buzzer) |
| App driver | `src/raspberry_pab/matrix_controller.py`, `routes/matrix.py` |
| Wiring docs | `hardware/esp32/WIRING.md` |
| Mobile / battery | `hardware/power/MOBILE-POWER.md` — AC2A + Cywhrvzsf 5.1 V rail |
| Legacy Nano (2 panels) | `hardware/arduino/` — **512** LEDs only; do not bump Nano to 768 |

Daisy-chain: panel1 **DOUT →** panel2 **DIN →** panel3 **DIN**, shared 5V/GND → one **8×96** (768 LED) strip. Env: `PAB_MATRIX_ENABLED`, width **96**, port empty → uses buzzer port (combined board).

**Nano SRAM:** 768×3 = **2304 B** does **not** fit ATmega328P. Legacy Nano stays at 512 / width 64.

## Serial protocol (unchanged from Nano)

Commands (newline-terminated): `PING`, `INFO`, `STOP`/`CLEAR`, `BEEP …`, `BRIGHT n`, `SOLID r g b ms`, `FLASH r g b ms interval`, `CHASE r g b ms`, `SCROLL r g b ms [mode] text`, `SCROLLONCE r g b [mode] text`, `RAINBOW ms`.

- `SCROLL` optional `mode`: `0` solid, `1` rainbow, `2` pulse.
- `SCROLLONCE`: one full pass across the matrix then clear (no wrap loop).
- `RAINBOW`: animate a full-panel color wheel for `ms`.
- Replies: `PONG`, `PIXELS n FREE m`, `OK`, `ERR …`
- Handshake: accept any line `READY` or starting with `READY `; then `PING`→`PONG`.
- Boot banner: `READY PIXELS 768 FREE …`
- Hold `HARDWARE_SERIAL_LOCK` across buzzer + matrix transactions.

## Python wait times

```text
scroll_timeout = max(duration_ms / 1000 * 2 + 5, 15)
```

Firmware scroll advances by **frame count** (`ms / SCROLL_MS`). Sanitize message to ~**36** printable ASCII chars.

## Deploy / verify on kiosk Pi

```bash
sudo systemctl stop raspberry-pab
PAB_BUZZER_PORT=/dev/ttyUSB0 ./scripts/upload-esp32-matrix-test.sh   # optional wiring check
PAB_BUZZER_PORT=/dev/ttyUSB0 ./scripts/upload-esp32-hardware.sh
sudo systemctl start raspberry-pab
```

Port is often CP2102: `/dev/ttyUSB0` or `/dev/serial/by-id/usb-Silicon_Labs_CP210*-if00-port0`.

### Checklist

1. `matrix_test` lights all three panels → power/data OK.
2. Production: `PIXELS 768`, SOLID red across full width, SCROLL readable.
3. Admin **Test matrix** + **Test buzzer** on the same USB-C port.
4. Common GND; matrix **not** on ESP32 `5V`.

## Adding a new matrix effect

1. Implement in ESP32 firmware (heap is fine; still avoid huge globals).
2. Add command parser branch with `startsWith` + `parseInt` (no `sscanf` required, but keep parsers tiny).
3. Add `build_*_command` in `matrix_controller.py` if the app should drive it.
4. Keep SCROLL as the reminder path unless deliberately changing UX.
