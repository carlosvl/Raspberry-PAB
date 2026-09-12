# Bluetooth speaker audio

Raspberry-PAB can play reminder alerts and music breaks on a Bluetooth A2DP speaker. Pair once from **Admin → Sounds → Bluetooth speaker** (PIN required; works from a phone over Wi‑Fi, including Roku-only field kits with no HDMI).

## Playback preference

1. `PAB_SOUND_SINK` — if set, always use that PipeWire/Pulse sink
2. Connected BlueZ sink (`bluez_output.*`) — preferred when a speaker is connected
3. HDMI sink — fallback (current auto-detect)

Music breaks use the same `SoundController` path, so they follow the same sink.

## Pair once (Admin)

1. Put the speaker in pairing mode.
2. Open **Admin → Sounds → Bluetooth speaker**.
3. Tap **Scan Nearby**, then **Pair** / **Connect**.
4. Confirm **Playback sink** shows a `bluez_output…` name and `source=bluetooth`.
5. Use **Test** on a library sound (or **Test alert sound** on a rule).

The last connected MAC/name are stored in SQLite (`bt_speaker_mac`, `bt_speaker_name`). On service start the Pi tries a best-effort reconnect if that MAC is saved (speaker must be powered and in range).

## Field reconnect

- Power on the speaker near the Pi; use **Connect** on the paired list if it does not auto-join.
- **Disconnect** leaves the device paired; **Forget** removes it and clears the saved preference.

## Install / CLI

`scripts/install.sh` installs `bluez` and `pulseaudio-utils` (for `pactl`), copies `manage-pi-bluetooth.sh` to `~/bin`, and adds a sudoers NOPASSWD rule (same pattern as Wi‑Fi).

After connect, the helper switches the BlueZ card to **A2DP** and waits for a `bluez_output.*` PipeWire sink (talks to the desktop user’s session via `XDG_RUNTIME_DIR`, not root).

```bash
~/bin/manage-pi-bluetooth.sh status --json
~/bin/manage-pi-bluetooth.sh scan --json
~/bin/manage-pi-bluetooth.sh pair AA:BB:CC:DD:EE:FF
~/bin/manage-pi-bluetooth.sh connect AA:BB:CC:DD:EE:FF
```

## Override sink

```bash
# Force a specific sink (wins over Bluetooth and HDMI)
PAB_SOUND_SINK=bluez_output.aa_bb_cc_dd_ee_ff.a2dp_sink
```

List sinks: `pactl list short sinks`.

## Troubleshooting

| Symptom | What to check |
|---------|----------------|
| No devices on Scan | Wait for the ~12s scan; speaker in pairing/range; retry |
| Connect fails / busy | Speaker may already be linked — Disconnect, wait 2s, Connect again |
| No `bluez_output` after connect | Needs A2DP + `pulseaudio-utils` (`pactl`); wait ~10s; check `pactl list short sinks` |
| Adapter off / blocked | `rfkill list`; `bluetoothctl show` → Powered: yes |
| Pair fails | Speaker in pairing mode; forget old phone pairing; retry scan |
| Sound still on HDMI | Status should show `source=bluetooth`; unset `PAB_SOUND_SINK` if it points at HDMI |
| Script / 502 from Admin | Re-run install for sudoers; `sudo -n ~/bin/manage-pi-bluetooth.sh status --json` |
| Service cannot see PipeWire | systemd unit must set `XDG_RUNTIME_DIR=/run/user/<uid>` (installer does this) |

ESP32 buzzer / matrix audio is separate from this PipeWire path.
