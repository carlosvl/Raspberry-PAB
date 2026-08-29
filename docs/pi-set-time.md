# Set Pi system time over SSH

Reminders and the kiosk board use the Pi’s **system clock**. Fix time/timezone over SSH when NTP is wrong or the Pi has been offline.

## Check current time

```bash
ssh carlos@192.168.4.49
timedatectl
date
```

## Set timezone (once)

Example US Central:

```bash
sudo timedatectl set-timezone America/Chicago
timedatectl
```

List zones: `timedatectl list-timezones | grep -i america`

## Prefer automatic sync (NTP)

```bash
sudo timedatectl set-ntp true
timedatectl status
```

Wait a few seconds, then `date` should match real time if the Pi has network.

## Set the clock manually (no reliable NTP)

Turn NTP off, set local time, turn NTP back on if you want:

```bash
sudo timedatectl set-ntp false
sudo timedatectl set-time '2026-08-29 10:34:00'
sudo timedatectl set-ntp true   # optional; skip if offline
date
```

Format is `YYYY-MM-DD HH:MM:SS` in the **configured timezone**.

## After changing time

Restart the kiosk service so schedulers pick up the new clock:

```bash
sudo systemctl restart raspberry-pab
```

## Note: admin “Test Lab” simulated clock

Admin can also run a **simulated** kiosk clock for race-day testing. That does **not** change the OS clock. For real events, use `timedatectl` as above and clear any simulated clock in Admin → Test Lab.
