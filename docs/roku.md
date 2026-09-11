# Roku TV board (sideloaded channel)

HDMI remains the primary kiosk display. When a Pi has **no HDMI monitor**, it auto-discovers a Roku on the same network and launches the sideloaded **Raspberry-PAB** channel. Admin stays on the iPhone `/admin` PWA.

The Roku channel is a **native SceneGraph board** (same schedule data as the kiosk, kiosk-like layout and row colors). It is **not** a mirror of the HDMI Chromium window.

| At boot | What runs |
|---------|-----------|
| HDMI connected | Chromium kiosk on the monitor (unchanged). Auto-cast stays off. |
| No HDMI | Pi launches the sideloaded Roku channel with the Pi’s LAN URL. |

Manual **Admin → TVs → Show board** still works even with HDMI plugged in (clubhouse TV + local monitor).

## What survives TV power off / on

| Item | Survives normal power cycle? |
|------|------------------------------|
| Sideloaded **Raspberry-PAB** channel | Yes — stays installed |
| Developer mode | Yes |
| **Control by mobile apps → Network access = Default** | Yes |
| Channel **open on screen** | No — TV returns to Home; Pi auto-cast (or Show board) re-opens it |
| Factory reset | Wipes sideload — run `sideload-roku-channel.sh` again |

## Once at home (per Roku)

1. On the Roku remote: press **Home** five times, then **Up**, **Right**, **Down**, **Left**, **Up** to open the developer secret screen (or use **Settings → System → Advanced system settings → Developer options** if already enabled).
2. Enable the installer / developer mode and set a password. Note the Roku’s IP.
3. Set **Settings → System → Advanced system settings → Control by mobile apps → Network access** = **Default** (not Limited). Limited mode blocks ECP launch and app queries.
4. From a laptop on the same Wi‑Fi:

```bash
./scripts/sideload-roku-channel.sh <roku-ip>
# prompts for the developer password, or:
# ROKU_PASSWORD='…' ./scripts/sideload-roku-channel.sh <roku-ip>
```

5. Confirm **Raspberry-PAB** appears on the Roku home row (sideloaded apps use id `dev`).

## Field day (no HDMI)

1. Power the Pi. `raspberry-pab` starts over systemd. Chromium may fail without a monitor — that is fine.
2. Put the **Roku on the same network as the Pi**:
   - Venue Wi‑Fi (avoid guest **client isolation**), or
   - Join the Pi hotspot `Raspberry-PAB` / `RaspberryPAB123` and use `http://10.42.0.1:8080`
3. Within ~15–20 seconds the Pi SSDP-discovers the TV and POSTs  
   `http://ROKU:8060/launch/dev?contentId=http://<pi-ip>:8080`
4. The channel shows **Connecting…**, then the live board (polls `GET /api/tv-board` every ~2s): title, logo, schedule table, countdown, results, reminder overlay.
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

## Update the channel after code changes

Re-sideload whenever `roku/pab-channel/` changes, then launch with the Pi’s LAN URL:

```bash
ROKU_PASSWORD='your-dev-password' ./scripts/sideload-roku-channel.sh <roku-ip>
curl -d '' "http://<roku-ip>:8060/launch/dev?contentId=http%3A%2F%2F<pi-ip>%3A8080"
```

Or use **Admin → TVs → Show board** after sideload.

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
| TV never launches / ECP 404 | **Network access** must be **Default**, not Limited |
| Connecting / Reconnect errors | Same LAN? Open `http://<pi-ip>:8080/api/tv-board` from a phone on that Wi‑Fi |
| Auto-cast with HDMI | Expected off in `hdmi-fallback`; use **Show board** or mode **Always on** |
| Guest Wi‑Fi fails | Client isolation blocks Pi↔Roku; use private Wi‑Fi or the Pi hotspot |
| Board looks unlike HDMI | Expected — native channel, not Chromium cast. Layout tracks the kiosk; re-sideload after channel updates |
| Channel missing after reset | Factory reset wipes sideload — install again |

## Channel source

BrightScript / SceneGraph package: [`roku/pab-channel/`](../roku/pab-channel/).
