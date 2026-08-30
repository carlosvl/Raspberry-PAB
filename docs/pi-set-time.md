# Set Pi system time

Reminders and the kiosk board use the Pi’s **system clock**. Fix time/timezone when NTP is wrong or the Pi has been offline.

## Prefer Admin UI (gamepad-friendly)

On the kiosk or remote admin:

1. Unlock Admin → **Kiosk Branding** → **System clock**
2. Use **− / +** steppers (gamepad click works) for year / month / day / hour / minute
3. Tap **Set Pi System Time**

That runs `~/bin/set-pi-system-time.sh` (passwordless sudo), which:

- Sets the OS clock
- Turns **NTP off** (stays off across reboot)
- Runs **`fake-hwclock save`** so the time is restored on the next boot even with **no network**
- Clears any Test Lab simulated clock

Pi boards usually have **no battery RTC**. Without `fake-hwclock`, a reboot offline would jump the clock backward. `install.sh` installs and enables it; the set-time helper also saves immediately after each manual set.

Expect the clock after reboot to be roughly the last saved time (shutdown / last hourly save / last admin set), not wall-clock perfect if the Pi was powered off for a while.

## Check current time (SSH)

```bash
ssh carlos@raspberry-b-kiosk.local
timedatectl
date
cat /etc/fake-hwclock.data
```

## Set timezone (once)

Example US Central:

```bash
sudo timedatectl set-timezone America/Chicago
timedatectl
```

List zones: `timedatectl list-timezones | grep -i america`

## Prefer automatic sync (NTP) when online

```bash
sudo timedatectl set-ntp true
timedatectl status
```

Wait a few seconds, then `date` should match real time if the Pi has network.

## Set the clock manually over SSH

```bash
sudo ~/bin/set-pi-system-time.sh set '2026-08-29 10:34:00'
```

Format is `YYYY-MM-DD HH:MM:SS` in the **configured timezone**.

## After changing time

Usually no service restart is required (schedulers read OS time each tick). If the board looks stuck, use Admin → **Restart Service** or:

```bash
sudo systemctl restart raspberry-pab
```

## Note: admin “Test Lab” simulated clock

Admin can also run a **simulated** kiosk clock for race-day testing. That does **not** change the OS clock. Setting the real system clock from Branding clears the simulation. For real events, keep Test Lab on real time.
