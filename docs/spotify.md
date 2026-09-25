# Spotify playback

The Pi can play Spotify music on the same speaker as alerts (Bluetooth first, then HDMI). It runs [go-librespot](https://github.com/devgianlu/go-librespot) as a Spotify Connect receiver named **PAB Board**.

## Requirements

- **Spotify Premium.** Spotify Connect receivers only work with Premium accounts.
- **Internet.** Spotify streams, so it can't play offline or on the fallback hotspot. When Spotify is offline, the local **music breaks** play as before.
- To see **PAB Board** in the Spotify app, your phone must be on the same Wi-Fi as the Pi.

## Install (once, on the Pi)

Run this as the **kiosk desktop user**, the same user `raspberry-pab` runs as (`pi` by default, `carlos` on some kiosks), so the service can use that user's PipeWire session:

```bash
cd ~/Raspberry-PAB
./scripts/install-spotify.sh
```

The script:

- installs the go-librespot binary to `/usr/local/bin/go-librespot` (pinned version; `--version vX.Y.Z` to change)
- writes `~/.config/go-librespot/config.yml` (kept on re-runs; `--force-config` to overwrite)
- installs and starts the **user** service `pab-spotify` (`deploy/systemd/pab-spotify.service`). It runs in the desktop user's session, so it can reach PipeWire and the Bluetooth sink.

The config binds the control API to `127.0.0.1:3678` only, so only the kiosk server on the Pi can control it.

## Log in (once)

The service uses Spotify's **device code** login, so the Pi doesn't need a keyboard or browser:

1. On the Pi, run `curl -s 127.0.0.1:3678/auth/code`, or watch `journalctl --user -u pab-spotify -f`, to get the code.
2. On your phone, open **spotify.com/pair** and enter the code.
3. The credentials are saved in `~/.config/go-librespot/state.json` and are reused after reboots.

Once logged in, the kiosk can start playlists by itself, without a phone. You can still pick **PAB Board** from the Spotify app to play from your phone.

## Check

```bash
systemctl --user status pab-spotify
curl -s 127.0.0.1:3678/status
```

`/status` returns **204 No Content** until the login is done, and JSON with `username` and the current `track` after that.

## How the kiosk uses Spotify

Turn it on with `PAB_SPOTIFY_ENABLED=1` in `.env` (or from the Admin page once it has a Spotify section), then restart `raspberry-pab`. The server talks to go-librespot at `PAB_SPOTIFY_API_URL` (default `http://127.0.0.1:3678`).

- **Online** means Spotify is enabled, go-librespot answers, and it is logged in. The status is re-checked about every 10 seconds.
- **Alerts:** if Spotify is playing when a reminder fires, it pauses, the alert plays, and Spotify resumes afterward. If it was already paused, it stays paused.
- **Music breaks** only play when Spotify is **offline**. While Spotify is online, each break slot is skipped (and never plays late).
- **Speaker:** go-librespot plays to PipeWire's default output. While it plays, the server moves its stream to the same output alerts use (saved Bluetooth speaker, then HDMI), if that output exists.

## Troubleshooting

- **No sound:** confirm `pactl list short sinks` shows the Bluetooth or HDMI sink, and that alert sounds play there. go-librespot uses the default Pulse sink.
- **Service not running after boot:** the user service starts with the desktop session, which kiosk autologin provides. To start it without a login, run `sudo loginctl enable-linger <kiosk user>`.
- **Service keeps restarting:** stop it and run `/usr/local/bin/go-librespot` in the foreground to see the error.
- **Login or streaming fails:** check that the Pi's clock is right (`timedatectl` should show `System clock synchronized: yes`), because Spotify's secure connections fail when the clock is far off.
- **PAB Board missing in the Spotify app:** the phone and Pi must be on the same network, and mDNS (port 5353/udp) must not be blocked.
