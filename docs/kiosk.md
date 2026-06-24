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
│  listens on 0.0.0.0:8080 for iOS admin │
└─────────────────────────────────────────┘
```

## 1. Enable desktop autologin

On the Pi, run:

```bash
sudo raspi-config
```

Go to **System Options → Boot / Auto Login → Desktop Autologin**.

The kiosk browser only starts when a graphical session is active.

## 2. Screen blanking and sleep

`scripts/install.sh` disables Raspberry Pi OS screen blanking and the `raspberry-pab` systemd unit blocks idle/system sleep while the app is running.

While the service is active it:

- wraps the server with `systemd-inhibit` so the OS does not suspend or idle-sleep
- runs `scripts/keep-awake.sh` in the background to disable DPMS/screen blanking on `:0` and `:1`

The kiosk browser launchers (`scripts/kiosk.sh` and `scripts/kiosk-touch.sh`) also call `keep-awake.sh` when Chromium starts.

If you need to tune the refresh interval, set `PAB_KEEP_AWAKE_INTERVAL` (seconds, default `45`) in `.env`.

For manual setup on an existing Pi without re-running the installer:

```bash
sudo raspi-config nonint do_blanking 1
sudo apt install x11-xserver-utils
./scripts/keep-awake.sh apply
sudo systemctl restart raspberry-pab
```

On X11 sessions you can also run:

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

For an iPhone on the same Wi-Fi, use the remote URL shown on the kiosk screen, for example:

```text
http://192.168.4.72:8080/admin
```

The default admin PIN is `1234`. Set `PAB_ADMIN_PIN` in `.env` before deployment.

The admin screen supports:

- Adding, editing, and deleting names with date/start time
- Adding reminder rules such as `30 min: Warm Up {name}`
- Optional repeating reminders, for example every 5 minutes from 15 minutes before start
- JSON import/export for offline setup or backups

On the Pi touchscreen, tap **Keyboard** on the admin PIN screen or admin header to open the OS on-screen keyboard. The installer tries to install `wvkbd`, `matchbox-keyboard`, or `onboard`; the app launches whichever is available for the active desktop session.

Example import file: `data/schedule.example.json`.

## 5. Remote iOS app and fallback hotspot

The admin UI is installable on iOS as a Safari PWA:

1. Connect the iPhone to the same Wi-Fi as the Pi.
2. Open the kiosk's displayed remote `/admin` URL.
3. Enter the admin PIN.
4. In Safari, choose **Share → Add to Home Screen**.

If the Pi is not connected to a known Wi-Fi network, the `pab-autohotspot.timer` starts the `Raspberry-PAB` hotspot through NetworkManager. Connect the iPhone to that hotspot and open:

```text
http://10.42.0.1:8080/admin
```

The default hotspot password is `RaspberryPAB123`. Override `PAB_HOTSPOT_SSID` and `PAB_HOTSPOT_PASSWORD` in `.env` before running `scripts/install.sh`.

Check hotspot status with:

```bash
systemctl status pab-autohotspot.timer
journalctl -u pab-autohotspot.service
nmcli connection show PAB-Hotspot
```

## 6. Customize the UI

Edit files under `web/`:

| Path | Purpose |
|------|---------|
| `web/index.html` | Page structure |
| `web/css/kiosk.css` | Fullscreen touch styling |
| `web/js/kiosk.js` | Client-side logic |
| `web/admin.html` | Admin page |
| `web/js/admin.js` | Admin behavior |

Add API routes under `src/raspberry_pab/routes/` for buttons, sensors, or backend data.

## 7. Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PAB_DISPLAY_TITLE` | `Raspberry-PAB` | Title shown on the kiosk display |
| `PAB_HOST` | `127.0.0.1` | Local URL host used by Chromium |
| `PAB_BIND_HOST` | `0.0.0.0` | Address uvicorn listens on for remote access |
| `PAB_PORT` | `8080` | Server port |
| `PAB_KIOSK_URL` | `http://127.0.0.1:8080` | URL opened by Chromium |
| `PAB_WEB_DIR` | `./web` | Static files directory |
| `PAB_DATA_DIR` | `~/.local/share/raspberry-pab` | SQLite DB location |
| `PAB_ADMIN_PIN` | `1234` | PIN for admin writes |
| `PAB_HOTSPOT_SSID` | `Raspberry-PAB` | Fallback hotspot name |
| `PAB_HOTSPOT_PASSWORD` | `RaspberryPAB123` | Fallback hotspot password |

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
