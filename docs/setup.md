# Setup guide

## Raspberry Pi OS kiosk

1. Flash **Raspberry Pi OS** (64-bit recommended).
2. Clone this repo and run `./scripts/install.sh`.
3. Enable **desktop autologin**: `sudo raspi-config` → System Options → Boot / Auto Login.
4. Start the server: `sudo systemctl enable --now raspberry-pab`.
5. Reboot — Chromium should open fullscreen to the kiosk UI.

Full details: [kiosk.md](kiosk.md)

## Development on Mac/Linux

The kiosk UI is plain HTML/CSS/JS. Run the server locally and preview in any browser:

```bash
make install-dev
make run
# open http://127.0.0.1:8080
# open http://127.0.0.1:8080/admin for schedule setup
```

Use the admin page to enter participants and reminder rules, or import `data/schedule.example.json` as a starting point.

## Adding features

| Need | Where to add it |
|------|-----------------|
| UI screens, buttons, layout | `web/` |
| Schedule API, GPIO, backend logic | `src/raspberry_pab/routes/` |
| Reminder timing | `src/raspberry_pab/reminders.py` |
| Settings | `src/raspberry_pab/config.py` + `.env` |

## GPIO / hardware (optional)

Install inside the project venv on the Pi:

```bash
source .venv/bin/activate
pip install gpiozero
```

Expose hardware through API routes in `server.py`; call them from `web/js/kiosk.js`.
