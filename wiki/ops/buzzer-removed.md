---
title: Buzzer removed
type: decision
sources:
  - src/raspberry_pab/server.py
  - src/raspberry_pab/arduino_serial.py
  - src/raspberry_pab/db.py
  - hardware/esp32/WIRING.md
  - user (2026-10-02)
updated: 2026-10-02
---

# Buzzer removed

The user asked to trim unneeded code, so the app no longer drives the buzzer (2026-10-02, branch `chore/deprecate-buzzer`). Scope chosen: code plus buzzer-only files, **firmware untouched**.

## Removed

- `buzzer_controller.py`, `routes/buzzer.py` (`POST /api/admin/buzzer/test`), their tests, the `BuzzerTest` model, and the six per-rule `buzzer_*` fields (models, SQL, export/import, Admin rule form, rule summary, **Test buzzer** button).
- Settings `buzzer_enabled`, `buzzer_port`, `buzzer_mode`, `buzzer_baud` (env `PAB_BUZZER_*`) and the buzzer keys of `/api/admin/hardware-status`.
- The buzzer step in `play_alert_groups`. Rule alerts still do LED, **sound** and matrix.
- Buzzer-only legacy sketches (`hardware/arduino/raspberry_pab_buzzer`, `buzzer_silent`, `buzzer_test`, `buzzer_pin_test`) and the scripts `upload-buzzer.sh` and `configure-buzzer-pi.sh`.

## Matrix port: the one coupling

`effective_matrix_port()` used to fall back to `buzzer_port`, because the ESP32 matrix and buzzer share one USB port. It now returns `matrix_port` only. **Set `PAB_MATRIX_PORT`.** The Pi already has `PAB_MATRIX_PORT=/dev/ttyUSB0` (checked 2026-10-02), so it's unaffected. Leftover `PAB_BUZZER_*` lines in a `.env` are ignored.

## Left in place on purpose

- **Firmware** (`hardware/esp32/...`, `hardware/arduino/raspberry_pab_hardware`) still handles `BEEP`/`STOP`, so nothing needs flashing. The wiring docs still describe the buzzer pin.
- `scripts/detect-buzzer-port.sh` and the `upload-esp32-*` and `upload-hardware.sh` scripts keep their names. They accept `PAB_MATRIX_PORT` (and still `PAB_BUZZER_PORT` as a fallback).
- **Database:** existing `reminder_rules` rows keep their `buzzer_*` columns (they have defaults, so inserts without them work). New databases don't create them. `tests/test_buzzer_removed.py` covers both cases and an old export with `buzzer_*` keys (ignored on import).
- `CLAUDE.md` and `.claude/rules/*` still mention the buzzer; they are the user's schema files, so they were not edited.
