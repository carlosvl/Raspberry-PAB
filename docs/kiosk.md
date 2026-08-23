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

Open `/admin` from the kiosk by tapping the logo or title three times, or browse directly to:

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

### USB gamepad as mouse

Plug a USB game controller into the Pi. In **Admin → Touch**, enable **Gamepad as mouse** and save. The left stick moves the HDMI cursor; the primary face button (usually index `1` on generic USB pads) is a left click and the next button is a right click. Override with `PAB_GAMEPAD_BTN_LEFT` / `PAB_GAMEPAD_BTN_RIGHT` in `touch-map.conf` if your pad differs.

The helper runs as `~/bin/gamepad-mouse.py` and is started automatically when the kiosk service starts (or when you save touch settings). Tune pointer speed and stick deadzone in the same panel. When the cursor reaches the screen edge and you keep pushing the stick, the page scrolls (`PAB_GAMEPAD_EDGE_MARGIN`, `PAB_GAMEPAD_SCROLL_SENS` in `touch-map.conf`). Logs: `/tmp/gamepad-mouse.log`.

Example import file: `data/schedule.example.json`.

## 5. Remote iOS app and fallback hotspot

See **[pi-wifi.md](pi-wifi.md)** for changing the Pi’s Wi-Fi (e.g. joining **QualitySuites** via the fallback hotspot first).

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

## 6.1 BLE LED strip alerts

Raspberry-PAB can flash a **Lotus Lamp X / MELK** BLE LED strip when reminder rules fire.

1. Add device settings to `.env` on the Pi:

```bash
PAB_LED_ENABLED=true
PAB_LED_ADDRESS=BE:28:79:00:06:CB
PAB_LED_NAME="MELKL-OT21 CB"
```

2. In `/admin` → **Rules**, enable **Flash LED strip** per rule and set:
   - **LED color**
   - **Flash interval (ms)** — lower values flash faster
   - **Flash duration (seconds)** — defaults to 10 seconds to match the kiosk alert overlay
   - **Chase duration (seconds)** — after flashing, runs the strip back and forth (default 10s; set to 0 to skip)
   - Use **Test LED strip** to preview the current color and timing without waiting for a reminder

3. Close the Lotus Lamp X iPhone app while the kiosk runs — the controller accepts only one BLE connection at a time.

4. Smoke-test BLE from the project venv:

```bash
.venv/bin/python scripts/test-lotus-lamp.py
```

## 6.2 ESP32 buzzer + WS2812 matrix

Production hardware is a **combined ESP32 board** (buzzer GPIO **4**, matrix DIN GPIO **16**, **768** LEDs = three 8×32 panels). Wiring: [hardware/esp32/WIRING.md](../hardware/esp32/WIRING.md). Field power: [hardware/power/MOBILE-POWER.md](../hardware/power/MOBILE-POWER.md).

1. Add to `.env` on the Pi:

```bash
PAB_BUZZER_ENABLED=true
PAB_BUZZER_PORT=/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0
PAB_MATRIX_ENABLED=true
PAB_MATRIX_WIDTH=96
PAB_MATRIX_BRIGHTNESS=64
```

(`PAB_MATRIX_PORT` can stay empty — it uses the buzzer port.)

2. Flash firmware (stop the service first on the Pi):

```bash
sudo systemctl stop raspberry-pab
PAB_BUZZER_PORT=/dev/ttyUSB0 ./scripts/upload-esp32-matrix-test.sh   # optional wiring check
PAB_BUZZER_PORT=/dev/ttyUSB0 ./scripts/upload-esp32-hardware.sh
sudo systemctl start raspberry-pab
```

On a Mac, use `/dev/cu.usbserial-*` or run `./scripts/detect-buzzer-port.sh`. The Pi needs internet for `arduino-cli` on first flash; otherwise flash from the Mac and plug the ESP32 back into the Pi.

3. Confirm boot line on serial: `READY PIXELS 768`. Use **Admin → Test buzzer** and **Test matrix**.

Legacy Nano (two panels): [hardware/arduino/README.md](../hardware/arduino/README.md).

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
| `PAB_LED_ENABLED` | `false` | Enable BLE LED flashing on alerts |
| `PAB_LED_ADDRESS` | *(empty)* | BLE MAC address of the LED controller |
| `PAB_LED_NAME` | `MELKL-OT21 CB` | BLE advertised device name |
| `PAB_BUZZER_ENABLED` | `false` | Enable ESP32/Nano buzzer on alerts |
| `PAB_BUZZER_PORT` | *(empty)* | Serial port (CP2102 on ESP32) |
| `PAB_MATRIX_ENABLED` | `false` | Enable WS2812 matrix scroll on alerts |
| `PAB_MATRIX_WIDTH` | `96` | Matrix width (three 8×32 panels) |
| `PAB_MATRIX_BRIGHTNESS` | `64` | Matrix max brightness (field ≤128) |

See also [pi-wifi.md](pi-wifi.md) for hotspot + Wi-Fi changes.

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
