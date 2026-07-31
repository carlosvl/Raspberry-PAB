---
name: led-matrix-nano
description: >-
  Extend or debug the Raspberry-PAB dual 8×32 WS2812 matrix driven by Arduino
  Nano over USB serial. Use when changing matrix firmware, serial protocol,
  matrix_controller, admin Test matrix, upload scripts, or Nano RAM/layout
  issues (dark panels, OK without light, READY handshake, SCROLL timeouts).
---

# LED matrix (Nano + dual 8×32 WS2812)

## Architecture

| Piece | Path / role |
|-------|-------------|
| Production firmware | `hardware/arduino/raspberry_pab_hardware/` — buzzer D3 + matrix DIN D6 |
| Wiring smoke test | `hardware/arduino/matrix_test/` — wipe/rainbow, minimal BSS |
| Upload | `scripts/upload-hardware.sh`, `scripts/upload-matrix-test.sh` |
| Serial helpers | `src/raspberry_pab/arduino_serial.py` (shared with buzzer) |
| App driver | `src/raspberry_pab/matrix_controller.py`, `routes/matrix.py` |
| Wiring docs | `hardware/arduino/BREADBOARD-WIRING.md`, `hardware/arduino/README.md` |

Daisy-chain: panel1 **DOUT →** panel2 **DIN**, shared 5V/GND → one **8×64** (512 LED) strip. Env: `PAB_MATRIX_ENABLED`, width **64**, port empty → uses buzzer port.

## SRAM budget (root cause of most “dark panel” bugs)

Nano **2048 B** total:

1. Pixel buffer: `malloc(512*3)` = **1536 B** (NeoPixel constructor/`begin`).
2. BSS should stay ~**220 B** (Serial + strip object), matching `matrix_test`.
3. Stack left ≈ **250–300 B**. Anything heavier (GFX, `sscanf`, RAM string tables) smashes the buffer: `numPixels()==0` or garbage/`OK` with no light.

### What failed in practice

| Symptom | Cause |
|---------|--------|
| `READY PIXELS 0`, commands `OK`, panels dark | Heap malloc failed — BSS/.data too large (e.g. NeoMatrix, or command strings in `.data`) |
| `PIXELS 512` but SOLID dark / no `OK` | Stack overflow from `sscanf` into pixel buffer |
| Admin: brief red then nothing | Boot blink + handshake required exact `READY` while firmware sent `READY PIXELS…`, or debug kwargsarg crash |
| SCROLL sent, timeout, no `OK` | `show()` freezes `millis()`; wall time ≫ requested ms |

### Rules when adding features

- **No NeoMatrix/Adafruit_GFX** on this Nano for 512 LEDs.
- New protocol tokens: `PSTR` / `strcmp_P` / `F()` only — check `.data` with `avr-objdump -s -j .data` if unsure.
- Parse ints with small `strtol` helpers — never `scanf` family.
- Prefer effects that reuse the existing buffer; avoid large RAM framebuffers or fonts.
- If you need more RAM, options are: fewer LEDs, a bigger MCU, or dual-buffer strategies that still fit ~300 B stack.
- After firmware change: confirm compile line `Global variables use ~220 bytes` and runtime `INFO` → `PIXELS 512 FREE <positive>`.

## Serial protocol (current)

Commands (newline-terminated): `PING`, `INFO`, `STOP`/`CLEAR`, `BEEP …`, `BRIGHT n`, `SOLID r g b ms`, `FLASH r g b ms interval`, `CHASE r g b ms`, `SCROLL r g b ms text`.

- Replies: `PONG`, `PIXELS n FREE m`, `OK`, `ERR …`
- Handshake: accept any line `READY` or starting with `READY `; then `PING`→`PONG`.
- Opening the port may USB-reset the Nano; wait up to ~4s for READY.
- Hold `HARDWARE_SERIAL_LOCK` across buzzer + matrix transactions.

## Python wait times

```text
scroll_timeout = max(duration_ms / 1000 * 2 + 5, 15)
```

Firmware scroll should advance by **frame count** (`ms / SCROLL_MS`), not raw `millis()` end time.

SCROLL payload must fit 64-byte RX — sanitize to ~40 printable ASCII chars (`MAX_MATRIX_MESSAGE_CHARS`).

## Product behavior

- Reminders / **Test matrix**: scroll rendered message for `flash_duration + chase_duration` seconds.
- That is **not** BLE strip flash-then-chase; chase duration only extends matrix scroll time.
- Color/brightness from rule + `PAB_MATRIX_BRIGHTNESS`.

## Deploy / verify on kiosk Pi

```bash
sudo systemctl stop raspberry-pab
PAB_BUZZER_PORT=/dev/ttyUSB0 ./scripts/upload-hardware.sh
# optional wiring check:
PAB_BUZZER_PORT=/dev/ttyUSB0 ./scripts/upload-matrix-test.sh
sudo systemctl start raspberry-pab
```

Port is often `/dev/ttyUSB0` or `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`.

### Checklist

1. `matrix_test` lights both panels → power/data OK.
2. Production: `PIXELS 512`, SOLID red visible, SCROLL text readable across both panels.
3. Admin **Test matrix** scrolls message (no false “flash-only” from boot blink).
4. Buzzer still works on same Nano (lock + shared port).

## Adding a new matrix effect

1. Implement in firmware with **no new global buffers**; stack-local only, tiny.
2. Add command parser branch with `startsWith_P` + `parseInt`.
3. Add `build_*_command` in `matrix_controller.py` if the app should drive it.
4. Extend admin test only if product-facing; keep SCROLL as the reminder path unless deliberately changing UX.
5. Re-check BSS size and on-device `FREE` before merge.
