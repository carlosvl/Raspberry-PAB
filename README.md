# Raspberry-PAB

Fullscreen **offline schedule and reminder kiosk** for **Raspberry Pi OS**. A local web server serves a touch-friendly UI; Chromium runs in kiosk mode on boot.

## How it works

1. **Backend** — Python (FastAPI) stores schedules in local SQLite and serves `web/` on `http://127.0.0.1:8080`
2. **Frontend** — HTML/CSS/JS in `web/`, fullscreen and touch-ready
3. **Reminders** — named offset rules fire alerts before each start time
4. **Kiosk shell** — Chromium launches via desktop autostart with `--kiosk`
5. **Boot** — systemd starts the server; autologin + autostart opens the browser

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
├── data/schedule.example.json # Offline import example
├── deploy/
│   ├── systemd/               # Web server service
│   └── autostart/             # Chromium kiosk autostart
├── scripts/
│   ├── install.sh             # Pi install (chromium, unclutter, services)
│   └── kiosk.sh               # Launch fullscreen browser
└── docs/kiosk.md              # Full kiosk setup guide
```

## Quick start (development)

```bash
make install-dev
make run
```

Open http://127.0.0.1:8080 in your browser. Hold the top-right kiosk header for three seconds to open `/admin`, then use the admin PIN from `.env` (`1234` by default).

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

| Variable        | Default                        | Description              |
|-----------------|--------------------------------|--------------------------|
| `PAB_HOST`      | `127.0.0.1`                    | Server bind address      |
| `PAB_PORT`      | `8080`                         | Server port              |
| `PAB_KIOSK_URL` | `http://127.0.0.1:8080`        | URL for Chromium         |
| `PAB_WEB_DIR`   | `./web`                        | Static files directory   |
| `PAB_LOG_LEVEL` | `INFO`                         | Logging level            |
| `PAB_DATA_DIR`  | `~/.local/share/raspberry-pab` | App data path            |
| `PAB_ADMIN_PIN` | `1234`                         | PIN for admin writes     |

## License

MIT — see [LICENSE](LICENSE).
