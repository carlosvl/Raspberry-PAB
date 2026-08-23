# Raspberry-PAB

Fullscreen **offline schedule and reminder kiosk** for **Raspberry Pi OS**. A local web server serves a touch-friendly UI; Chromium runs in kiosk mode on boot.

## How it works

1. **Backend** — Python (FastAPI) stores schedules in local SQLite, serves the Pi kiosk on `http://127.0.0.1:8080`, and listens on the network for remote admin
2. **Frontend** — HTML/CSS/JS in `web/`, fullscreen and touch-ready
3. **Reminders** — named offset rules fire alerts before each start time
4. **Remote iOS admin** — Safari can open `/admin` over Wi-Fi and install it to the home screen as a PWA
5. **Kiosk shell** — Chromium launches via desktop autostart with `--kiosk`
6. **Boot** — systemd starts the server; autologin + autostart opens the browser

See [docs/kiosk.md](docs/kiosk.md) for autologin, screen blanking, and troubleshooting.

## Project structure

```
Raspberry-PAB/
├── web/                       # Kiosk UI (HTML, CSS, JS)
├── src/raspberry_pab/
│   ├── db.py                  # SQLite storage
│   ├── reminders.py           # Alert timing logic
│   ├── scheduler.py           # Background reminder loop
│   ├── server.py              # FastAPI routes + static files
│   ├── app.py                 # uvicorn server entry
│   └── config.py              # Env-based settings
├── hardware/
│   ├── esp32/                 # Production MCU: 3-panel matrix + buzzer
│   ├── arduino/               # Legacy Nano (2 panels)
│   └── power/                 # Mobile power + buck converter setup
├── data/schedule.example.json # Offline import example
├── deploy/
│   ├── systemd/               # Web server + fallback hotspot units
│   ├── network/               # NetworkManager hotspot helper
│   └── autostart/             # Chromium kiosk autostart
├── scripts/
│   ├── install.sh             # Pi install (chromium, unclutter, services)
│   ├── manage-pi-wifi.sh      # Wi-Fi status/scan/connect (admin + CLI)
│   ├── configure-pi-wifi.sh   # Thin CLI wrapper for manage-pi-wifi.sh
│   ├── upload-esp32-hardware.sh   # Flash combined ESP32 firmware
│   ├── upload-esp32-matrix-test.sh # ESP32 wiring smoke test
│   └── kiosk.sh               # Launch fullscreen browser
├── docs/kiosk.md              # Full kiosk setup guide
└── docs/pi-wifi.md            # Admin Wi-Fi tab + fallback hotspot
```

## Quick start (development)

```bash
make install-dev
make run
```

Open http://127.0.0.1:8080 in your browser. Tap the kiosk logo or title three times to open `/admin`, then use the admin PIN from `.env` (`1234` by default).

```bash
make test
cp .env.example .env   # optional local overrides
```

## Install on Raspberry Pi

```bash
git clone https://github.com/YOUR_USER/Raspberry-PAB.git
cd Raspberry-PAB
chmod +x scripts/*.sh
./scripts/install.sh
```

Then enable autologin (`sudo raspi-config`) and start the server:

```bash
sudo systemctl enable --now raspberry-pab
sudo reboot
```

The installer also creates a `Raspberry-PAB` Wi-Fi fallback hotspot. If the Pi cannot connect to a known Wi-Fi network, it broadcasts that hotspot and serves the app at `http://10.42.0.1:8080/admin`. On the Pi touchscreen, use **Admin → WiFi** to scan and join a network (local only). See [docs/pi-wifi.md](docs/pi-wifi.md).

## ESP32 buzzer + LED matrix (production)

Three daisy-chained **8×32 WS2812** panels (768 LEDs) plus an active buzzer run on a **38-pin ESP32-WROOM** (CP2102 USB) over one serial port to the Pi.

| Doc | Purpose |
|-----|---------|
| [hardware/esp32/WIRING.md](hardware/esp32/WIRING.md) | GPIO 16 (DIN), GPIO 4 (buzzer), power, daisy-chain |
| [hardware/power/MOBILE-POWER.md](hardware/power/MOBILE-POWER.md) | Field power (AC2A + Cywhrvzsf 5.1 V) |
| [hardware/power/CYWHRVZSF-BUCK-SETUP.md](hardware/power/CYWHRVZSF-BUCK-SETUP.md) | Buck pot calibration |

Flash firmware (Mac or Pi with `arduino-cli`):

```bash
PAB_BUZZER_PORT=/dev/ttyUSB0 ./scripts/upload-esp32-matrix-test.sh   # wiring check
PAB_BUZZER_PORT=/dev/ttyUSB0 ./scripts/upload-esp32-hardware.sh     # production
```

Set in `.env`: `PAB_BUZZER_ENABLED=true`, `PAB_MATRIX_ENABLED=true`, `PAB_MATRIX_WIDTH=96`, and `PAB_BUZZER_PORT` to the CP2102 by-id path. Test from **Admin → Test buzzer** / **Test matrix**.

Legacy **Arduino Nano** (two panels, 512 LEDs): [hardware/arduino/](hardware/arduino/).

## Remote iOS admin

When the Pi is on your normal Wi-Fi, connect the iPhone to the same Wi-Fi and open the remote URL shown on the kiosk screen, such as:

```text
http://192.168.4.72:8080/admin
```

If normal Wi-Fi is unavailable, connect the iPhone to the `Raspberry-PAB` hotspot (default password `RaspberryPAB123`) and open:

```text
http://10.42.0.1:8080/admin
```

In Safari, use **Share → Add to Home Screen** to install it like an app. Admin changes still require the PIN.

## Offline schedule workflow

The app stores all schedules and reminder rules in SQLite under `PAB_DATA_DIR`, so it does not need internet access after installation.

Use `/admin` to add participants and rules, or import JSON with this shape:

```json
{
  "event_date": "2026-06-21",
  "participants": [
    { "name": "Carlos", "start_time": "11:00" }
  ],
  "reminder_rules": [
    { "offset_minutes": 30, "message_template": "Warm Up {name}" },
    { "offset_minutes": 15, "message_template": "Go to Start Line", "repeat_every_minutes": 5 }
  ]
}
```

For Carlos at 11:00, that example fires `Warm Up Carlos` at 10:30 and `Go to Start Line` at 10:45, 10:50, and 10:55.

## Race results

The admin **Race Results** panel syncs the [Precision Race MCA index](https://www.precisionrace.com/mca) and scrapes [ITS YOUR RACE](https://www.itsyourrace.com/) result pages for a selected race day. Participants are matched by calendar date and fuzzy name, then finish place/time appear on the kiosk board.

1. Open Admin → **Race Results**
2. Click **Sync MCA index**
3. Choose the race date and click **Sync results for date**

## Development commands

| Command            | Description                         |
|--------------------|-------------------------------------|
| `make run`         | Start kiosk web server              |
| `make install-dev` | Install package + dev tools         |
| `make test`        | Run tests with coverage             |
| `make lint`        | Run ruff linter                     |
| `make format`      | Auto-format code                    |
| `make typecheck`   | Run mypy                            |

## Configuration

| Variable                | Default                        | Description                                  |
|-------------------------|--------------------------------|----------------------------------------------|
| `PAB_DISPLAY_TITLE`     | `Raspberry-PAB`                | Title shown on the kiosk display             |
| `PAB_HOST`              | `127.0.0.1`                    | Local URL host used by Chromium              |
| `PAB_BIND_HOST`         | `0.0.0.0`                      | Address uvicorn listens on for remote access |
| `PAB_PORT`              | `8080`                         | Server port                                  |
| `PAB_KIOSK_URL`         | `http://127.0.0.1:8080`        | URL opened by Chromium                       |
| `PAB_WEB_DIR`           | `./web`                        | Static files directory                       |
| `PAB_LOG_LEVEL`         | `INFO`                         | Logging level                                |
| `PAB_DATA_DIR`          | `~/.local/share/raspberry-pab` | App data path                                |
| `PAB_ADMIN_PIN`         | `1234`                         | PIN for admin writes                         |
| `PAB_HOTSPOT_SSID`     | `Raspberry-PAB`                | Fallback hotspot name                        |
| `PAB_HOTSPOT_PASSWORD` | `RaspberryPAB123`              | Fallback hotspot password                    |
| `PAB_BUZZER_ENABLED`   | `false`                        | Enable buzzer on reminder alerts (ESP32 combined board) |
| `PAB_BUZZER_PORT`      | *(empty)*                      | Serial port for ESP32 (CP2102) / legacy Nano    |
| `PAB_BUZZER_MODE`      | `active`                       | `active` or `passive` buzzer module          |
| `PAB_BUZZER_BAUD`      | `115200`                       | Serial baud rate                             |
| `PAB_MATRIX_ENABLED`   | `false`                        | Enable WS2812 matrix on reminder alerts      |
| `PAB_MATRIX_PORT`      | *(empty)*                      | Serial port; defaults to `PAB_BUZZER_PORT`   |
| `PAB_MATRIX_WIDTH`     | `96`                           | Matrix width (three 8×32 panels daisy-chained) |
| `PAB_MATRIX_HEIGHT`    | `8`                            | Matrix height in pixels                      |
| `PAB_MATRIX_BRIGHTNESS`| `64`                           | Max matrix brightness (0–255; field ≤128)  |
| `PAB_MATRIX_BAUD`      | `115200`                       | Matrix serial baud rate                      |

On the Pi touchscreen, tap **Keyboard** on the admin PIN screen to open the installed OS on-screen keyboard. `scripts/install.sh` tries to install common keyboard packages (`wvkbd`, `matchbox-keyboard`, `onboard`) and `scripts/touch-keyboard.sh` launches whichever is available for the current desktop session.

## License

MIT — see [LICENSE](LICENSE).
