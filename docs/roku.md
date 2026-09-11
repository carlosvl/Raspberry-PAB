# Roku TV board (sideloaded channel)

HDMI remains the primary kiosk display. When a Pi has **no HDMI monitor**, it auto-discovers a Roku on the same network and launches the sideloaded **Raspberry-PAB** channel. Admin stays on the iPhone `/admin` PWA.

| At boot | What runs |
|---------|-----------|
| HDMI connected | Chromium kiosk on the monitor (unchanged). Auto-cast stays off. |
| No HDMI | Pi launches the sideloaded Roku channel with the Pi’s LAN URL. |

Manual **Admin → TVs → Show board** still works even with HDMI plugged in (clubhouse TV + local monitor).

## Once at home (per Roku)

1. On the Roku remote: press **Home** five times, then **Up**, **Right**, **Down**, **Left**, **Up** to open the developer secret screen (or use **Settings → System → Advanced system settings → Developer options** if already enabled).
2. Enable the installer / developer mode and set a password. Note the Roku’s IP.
3. Enable **Settings → System → Advanced system settings → Control by mobile apps → Network access** = **Default** (permissive).
4. From a laptop on the same Wi‑Fi:

```bash
./scripts/sideload-roku-channel.sh <roku-ip>
# prompts for the developer password
```

5. Confirm **Raspberry-PAB** appears on the Roku home row (sideloaded apps show as “dev”).

Developer mode survives normal reboots. A **factory reset** requires re-sideload.

## Field day (no HDMI)

1. Power the Pi. `raspberry-pab` starts over systemd. Chromium may fail without a monitor — that is fine.
2. Put the **Roku on the same network as the Pi**:
   - Venue Wi‑Fi (avoid guest **client isolation**), or
   - Join the Pi hotspot `Raspberry-PAB` / `RaspberryPAB123` and use `http://10.42.0.1:8080`
3. Within ~15–20 seconds the Pi SSDP-discovers the TV and POSTs  
   `http://ROKU:8060/launch/dev?contentId=http://<pi-ip>:8080`
4. The channel shows **Connecting…**, then the live board (polls `GET /api/tv-board` every 2s).
5. Manage the schedule from the phone: `http://<pi-ip>:8080/admin`

ESP32 matrix / buzzer keep working; they never needed HDMI.

## HDMI kiosk (unchanged)

Plug a monitor into the Pi. After reboot you get the normal Chromium fullscreen board. Auto-cast does not launch the Roku unless you change **Admin → TVs → Auto-cast** to **Always on**, or tap **Show board**.

## Admin → TVs

- **Scan TVs** — SSDP discovery + ECP device info
- **Show board / Home** — launch or leave the sideloaded channel
- **Auto-cast mode** — `hdmi-fallback` (default), `on`, or `off`
- **Allow auto-cast** — pause re-launch without changing the mode

If a TV shows **sideload needed**, run `./scripts/sideload-roku-channel.sh <ip>` from a laptop (ECP cannot push the zip).

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PAB_ROKU_ENABLED` | `true` | Master switch for Roku support |
| `PAB_ROKU_AUTOCAST` | `hdmi-fallback` | `on` / `off` / `hdmi-fallback` |
| `PAB_ROKU_CHANNEL_ID` | `dev` | Sideloaded channel id |
| `PAB_ROKU_SCAN_INTERVAL` | `15` | Autocast scan period (seconds) |

## Troubleshooting

| Symptom | Check |
|---------|--------|
| TV never launches | Same LAN? Control by mobile apps permissive? Channel sideloaded? |
| Connecting forever | Pi URL reachable from Roku? Try Admin → TVs preferred URL in a phone browser + `/api/tv-board` |
| Auto-cast with HDMI | Expected off in `hdmi-fallback`; use **Show board** or mode **Always on** |
| Guest Wi‑Fi fails | Client isolation blocks Pi↔Roku; use private Wi‑Fi or the Pi hotspot |

## Channel source

BrightScript / SceneGraph package: [`roku/pab-channel/`](../roku/pab-channel/).
