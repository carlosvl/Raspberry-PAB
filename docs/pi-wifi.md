# Change Pi Wi-Fi (NetworkManager)

Raspberry-PAB uses **NetworkManager** (`nmcli`). If the Pi is not on your network, use its **fallback hotspot** first, then join your Wi-Fi (e.g. **QualitySuites** or **SFDC-MN**).

Saved profiles on the kiosk Pi typically include venue networks such as **SFDC-MN** (autoconnect when in range). Add or update credentials with Admin → WiFi, or:

```bash
sudo nmcli connection add type wifi con-name "SFDC-MN" ifname wlan0 \
  ssid "SFDC-MN" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "YOUR_PASSWORD" \
  connection.autoconnect yes
# If the profile already exists, only update the password:
sudo nmcli connection modify SFDC-MN wifi-sec.key-mgmt wpa-psk wifi-sec.psk "YOUR_PASSWORD"
```

## Admin UI (Pi touchscreen)

Preferred when you are at the kiosk and only have touch or a gamepad:

1. On the HDMI display, open admin (triple-tap the logo/title, or open `/admin`).
2. Unlock with the admin PIN (on-screen keypad).
3. Open the **WiFi** tab.
4. Review **Current connection** and **Saved networks**.
5. Tap **Scan Nearby** (this briefly pauses the fallback hotspot so `wlan0` can scan).
6. Tap **Use this network**, then use the **in-admin Keyboard** (large on-screen keys) to type the password with touch or gamepad, then **Connect**.

Wi‑Fi password entry uses the **in-page keyboard** inside Admin → WiFi so gamepad-as-mouse can click keys in Chromium. It does not depend on the desktop OS keyboard (`wvkbd` / matchbox / onboard).

Wi‑Fi controls are **local-only** (they do not work from a phone on the hotspot). After a successful connect, the Pi leaves the hotspot and joins the chosen SSID; note the new IP on the status panel.

Saved NetworkManager profiles appear under **Saved networks** with **Connect** / **Forget**. The fallback hotspot profile (`PAB-Hotspot`) is never listed or deletable from this UI.

## Step 1 — Reach the Pi via hotspot

1. Power the Pi and wait ~2 minutes.
2. On your Mac, open **Wi‑Fi** and join:
   - **SSID:** `Raspberry-PAB` (default)
   - **Password:** `RaspberryPAB123` (default)
3. SSH:

```bash
ssh carlos@10.42.0.1
```

If that fails, the Pi may still be on an old network or the hotspot name/password was customized in `.env` (`PAB_HOTSPOT_SSID`, `PAB_HOTSPOT_PASSWORD`).

## Step 2 — Connect the Pi to your Wi-Fi (SSH / CLI)

Prefer the **Admin UI** above when you are at the display. For SSH:

**Important:** While the Pi is broadcasting `Raspberry-PAB`, its Wi‑Fi radio cannot scan for other networks. The script stops the hotspot first, then **brings the hotspot back** after `--list` or a failed connect.

If you lose SSH after a scan, **power-cycle the Pi** (unplug 10s, plug back in). After ~2 minutes, rejoin `Raspberry-PAB` and `ssh carlos@10.42.0.1`.

From the Pi (SSH session):

```bash
cd ~/Raspberry-PAB/scripts
chmod +x configure-pi-wifi.sh manage-pi-wifi.sh

# See exact network names (stops hotspot — SSH may drop after connect)
./configure-pi-wifi.sh --list

# Connect (use the exact SSID from the list + real password)
./configure-pi-wifi.sh "QualitySuites" "YOUR_WIFI_PASSWORD"
```

Or call the JSON helper directly:

```bash
./manage-pi-wifi.sh status
./manage-pi-wifi.sh scan
./manage-pi-wifi.sh connect "QualitySuites" "YOUR_WIFI_PASSWORD"
```

Or manually:

```bash
sudo nmcli device wifi rescan
nmcli device wifi list
sudo nmcli device wifi connect "QualitySuites" password "YOUR_WIFI_PASSWORD"
ip -4 addr show wlan0
```

Note the new IP (e.g. `172.17.x.x` on QualitySuites).

## Step 3 — Rejoin the same Wi-Fi on your Mac

1. Disconnect from `Raspberry-PAB`.
2. Connect your Mac to **QualitySuites**.
3. SSH using the Pi’s new IP:

```bash
ssh carlos@172.17.x.x
```

Admin UI: `http://172.17.x.x:8080/admin`

## Hotel / captive portal (QualitySuites)

Some hotel networks need a browser login before internet works. The kiosk browser may need to open a random HTTP page once, or run on the Pi:

```bash
curl -I http://neverssl.com
```

Complete any login page in Chromium on the Pi if the network blocks outbound traffic until accepted.

## Useful checks

```bash
nmcli connection show --active
nmcli device status
systemctl status pab-autohotspot.timer
```

When the Pi is on a known Wi-Fi network, the fallback hotspot stays off. If Wi-Fi fails, `pab-autohotspot` brings `Raspberry-PAB` back within ~2 minutes.

## Mac: USB internet + Pi hotspot at the same time

Use **USB for internet** and **Wi‑Fi for the Pi** (`Raspberry-PAB` @ `10.42.0.1`). You do **not** need to turn Wi‑Fi off.

### 1. Connect both

1. Plug in USB (iPhone tethering, USB Ethernet, etc.) — confirm internet works.
2. Turn **Wi‑Fi on** and join **`Raspberry-PAB`** (`RaspberryPAB123`).
3. SSH: `ssh carlos@10.42.0.1`

### 2. Prefer USB for internet (service order)

**System Settings → Network → … (gear) → Set Service Order**

Drag **USB / iPhone USB** **above** **Wi‑Fi**. That makes the USB link the default route for the internet.

### 3. Route Pi traffic over Wi‑Fi

The Pi hotspot uses `10.42.0.0/24`. Send only that subnet via Wi‑Fi:

```bash
# Find Wi‑Fi interface name (usually en0)
networksetup -listallhardwareports | grep -A2 Wi-Fi

# Pin Pi subnet to Wi‑Fi (replace en0 if different)
sudo route -n add -net 10.42.0.0/24 -interface en0
```

### 4. Verify

```bash
# Internet → USB
route -n get default
ping -c 2 8.8.8.8

# Pi → Wi‑Fi
ping -c 2 10.42.0.1
ssh carlos@10.42.0.1
```

If SSH fails but ping works, try: `ssh -o BindAddress=$(ipconfig getifaddr en0) carlos@10.42.0.1`

The static route is lost after reboot. Re-run the `sudo route` command or add a small launch script if you use this often.

## Change hotspot defaults (optional)

In `.env` on the Pi before `scripts/install.sh`:

```bash
PAB_HOTSPOT_SSID=Raspberry-PAB
PAB_HOTSPOT_PASSWORD=RaspberryPAB123
```
