# Change Pi Wi-Fi (NetworkManager)

Raspberry-PAB uses **NetworkManager** (`nmcli`). If the Pi is not on your network, use its **fallback hotspot** first, then join your Wi-Fi (e.g. **QualitySuites**).

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

## Step 2 — Connect the Pi to your Wi-Fi

**Important:** While the Pi is broadcasting `Raspberry-PAB`, its Wi‑Fi radio cannot scan for other networks. The script stops the hotspot first, then **brings the hotspot back** after `--list` or a failed connect.

If you lose SSH after a scan, **power-cycle the Pi** (unplug 10s, plug back in). After ~2 minutes, rejoin `Raspberry-PAB` and `ssh carlos@10.42.0.1`.

From the Pi (SSH session):

```bash
cd ~/Raspberry-PAB/scripts
chmod +x configure-pi-wifi.sh

# See exact network names (stops hotspot — SSH may drop after connect)
./configure-pi-wifi.sh --list

# Connect (use the exact SSID from the list + real password)
./configure-pi-wifi.sh "QualitySuites" "YOUR_WIFI_PASSWORD"
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
