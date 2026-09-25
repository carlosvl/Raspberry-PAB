# Raspberry-PAB

An offline schedule and reminder kiosk for race day that runs on Raspberry Pi OS. A FastAPI backend stores data in SQLite. Chromium shows the board fullscreen from `web/`. Reminders drive a buzzer, a matrix of 3×8×32 WS2812 LED panels (both on an ESP32 over USB serial), a BLE LED strip, sounds (PipeWire, HDMI or Bluetooth), and a sideloaded Roku board as a fallback when HDMI is unplugged. The admin UI (`/admin`, PIN-gated) is used from an iPhone as a PWA over Wi-Fi or the fallback hotspot.

## Commands

```bash
make install-dev   # .venv + editable install with dev extras
make run           # server on http://127.0.0.1:8080 (admin: /admin, PIN from .env, default 1234)
make test          # pytest + coverage
make lint          # ruff check src tests
make typecheck     # mypy --strict
make format        # ruff format + fix
```

CI (`.github/workflows/ci.yml`) runs ruff, mypy, and pytest on Python 3.11–3.13. All three must pass.

## Layout

| Area | Path |
|------|------|
| App factory, lifespan, alert playback | `src/raspberry_pab/server.py` (`create_app(settings)`) |
| Env settings (frozen dataclass, `PAB_*`) | `src/raspberry_pab/config.py` |
| SQLite store + `app_settings` key/value | `src/raspberry_pab/db.py` (`ScheduleStore`) |
| Pydantic models | `src/raspberry_pab/models.py` |
| HTTP routes (one router per feature) | `src/raspberry_pab/routes/*.py` |
| Reminder loop / alert broker | `scheduler.py`, `reminders.py`, `alert_batch.py` |
| Hardware drivers | `arduino_serial.py`, `buzzer_controller.py`, `matrix_controller.py`, `led_controller.py` (BLE), `sound_controller.py`, `audio_sink.py` |
| Race results + MCA team scoring | `src/raspberry_pab/race_results/` |
| Roku | `roku_*.py`, `routes/roku.py`, `routes/tv_board.py`, `roku/pab-channel/` |
| Frontend (plain HTML/CSS/JS, no build step) | `web/index.html` + `web/js/kiosk.js` (board), `web/admin.html` + `web/js/admin.js` (admin) |
| Pi shell helpers (called by routes) | `scripts/manage-pi-wifi.sh`, `scripts/manage-pi-bluetooth.sh`, … |
| Firmware | `hardware/esp32/` (production), `hardware/arduino/` (legacy Nano) |
| Deploy | `deploy/systemd/raspberry-pab.service` (runs as `pi` from `/home/pi/Raspberry-PAB`), `scripts/install.sh` |

## Conventions

- Every module starts with a module docstring and `from __future__ import annotations`. Everything is fully typed, because mypy runs in strict mode. Ruff line length is 88.
- Routes use `APIRouter(prefix="/api", tags=[...])`. Admin writes depend on `require_admin_pin`, which checks the `X-Admin-Pin` header. Shared deps (`get_settings`, `get_store`) live in `routes/schedule.py`. Controllers are stored on `request.app.state`.
- Runtime-editable config lives in the `app_settings` DB table and falls back to the env `Settings`. `Settings` is frozen, so update it with `dataclasses.replace` on `app.state` (see `routes/led.py`).
- Hold `HARDWARE_SERIAL_LOCK` around any buzzer or matrix serial transaction, because both share one USB port.
- Tests use `fastapi.testclient.TestClient(create_app(Settings(data_dir=tmp_path/..., web_dir=...)))` and never touch real hardware. Scraper tests use HTML fixtures in `tests/fixtures/`.
- New features get a doc in `docs/`, or a README section, when they involve Pi setup or hardware steps.

## Working rules

- @.claude/rules/feature-scoped-edits.md applies to every task. Keep edits scoped to the feature and ask before touching unrelated features.
- For ESP32 or LED matrix work, see `.claude/rules/led-matrix.md` (auto-loaded for those paths) and the `led-matrix-esp32` skill.
- The Pi is reachable over the `raspberry-ssh` MCP server. Deploying, restarting `raspberry-pab`, or flashing firmware changes the live kiosk, so confirm with the user first.
