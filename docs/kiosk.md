# Kiosk setup on Raspberry Pi OS

Raspberry-PAB runs as a **local web server** plus a **fullscreen Chromium** window. The browser starts automatically when the `pi` user logs into the desktop, and the schedule/reminder data stays offline in SQLite.

## Architecture

```
┌─────────────────────────────────────────┐
│  Raspberry Pi OS desktop (autologin)    │
│  ┌───────────────────────────────────┐  │
│  │  Chromium (--kiosk, fullscreen)   │  │
│  │  → http://127.0.0.1:8080          │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
                    ▲
                    │ HTTP
┌───────────────────┴─────────────────────┐
│  raspberry-pab.service (systemd)        │
│  FastAPI + uvicorn + SQLite schedule DB │
└─────────────────────────────────────────┘
```

## 1. Enable desktop autologin

On the Pi, run:

```bash
sudo raspi-config
```

Go to **System Options → Boot / Auto Login → Desktop Autologin**.

The kiosk browser only starts when a graphical session is active.

## 2. Disable screen blanking

Add to `/etc/xdg/labwc/autostart` (Wayland / Bookworm default):

```bash
wlr-randr --output HDMI-A-1 --mode 1920x1080   # adjust if needed
```

To prevent the display from sleeping, create `/etc/systemd/system/disable-screen-blanking.service`:

```ini
[Unit]
Description=Disable screen blanking
After=graphical.target

[Service]
Type=oneshot
ExecStart=/usr/bin/setterm --blank 0 --powerdown 0

[Install]
WantedBy=graphical.target
```

Or use `xset` on X11 sessions:

```bash
xset s off
xset -dpms
xset s noblank
```

## 3. Start services

```bash
sudo systemctl enable --now raspberry-pab
sudo reboot
```

After reboot:

- **Server** starts via systemd before login
- **Chromium** launches via `~/.config/autostart/raspberry-pab-kiosk.desktop`

## 4. Manage the schedule

Open `/admin` from the kiosk by holding the top-right header area for three seconds, or browse directly to:

```text
http://127.0.0.1:8080/admin
```

The default admin PIN is `1234`. Set `PAB_ADMIN_PIN` in `.env` before deployment.

The admin screen supports:

- Adding, editing, and deleting names with date/start time
- Adding reminder rules such as `30 min: Warm Up {name}`
- Optional repeating reminders, for example every 5 minutes from 15 minutes before start
- JSON import/export for offline setup or backups

Example import file: `data/schedule.example.json`.

## 5. Customize the UI

Edit files under `web/`:

| Path | Purpose |
|------|---------|
| `web/index.html` | Page structure |
| `web/css/kiosk.css` | Fullscreen touch styling |
| `web/js/kiosk.js` | Client-side logic |
| `web/admin.html` | Admin page |
| `web/js/admin.js` | Admin behavior |

Add API routes under `src/raspberry_pab/routes/` for buttons, sensors, or backend data.

## 6. Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PAB_HOST` | `127.0.0.1` | Server bind address |
| `PAB_PORT` | `8080` | Server port |
| `PAB_KIOSK_URL` | `http://127.0.0.1:8080` | URL opened by Chromium |
| `PAB_WEB_DIR` | `./web` | Static files directory |
| `PAB_DATA_DIR` | `~/.local/share/raspberry-pab` | SQLite DB location |
| `PAB_ADMIN_PIN` | `1234` | PIN for admin writes |

## Troubleshooting

**Black screen after boot**

- Check server: `curl http://127.0.0.1:8080/api/health`
- Check logs: `journalctl -u raspberry-pab -f`

**Browser does not open**

- Confirm autologin is enabled
- Check autostart file: `~/.config/autostart/raspberry-pab-kiosk.desktop`
- Run manually: `./scripts/kiosk.sh`

**Wrong install path**

Re-run install or edit paths in:

- `deploy/systemd/raspberry-pab.service`
- `~/.config/autostart/raspberry-pab-kiosk.desktop`
