---
title: Music breaks removed
type: decision
sources:
  - src/raspberry_pab/server.py
  - src/raspberry_pab/sound_controller.py
  - src/raspberry_pab/led_controller.py
  - docs/spotify.md
  - user (2026-10-02)
updated: 2026-10-02
---

# Music breaks removed

With Spotify running, the user asked to deprecate music breaks (2026-10-02, branch `chore/deprecate-music-breaks`). The timed-playlist feature was **removed**, not disabled.

## Removed

- `music_break_scheduler.py`, `music_breaks.py`, `routes/music_breaks.py`, their tests, the `MusicBreak*` models, and the `/api/admin/music-breaks*` routes.
- Admin "Music breaks" tab and its JS. In `server.py`: scheduler construction, start/stop, the `music_break_scheduler` argument of `play_alert_groups`, and the broker hook that interrupted a break when an alert fired.

## Preserved: rule alert sounds

Rule sounds never depended on music breaks. When a rule fires, `play_alert_groups` calls `sound_controller.play(rule)`, which plays the sound chosen on the rule (`sound_enabled`, `sound_id`, `sound_volume`). The sound library, Bluetooth sink choice, `SoundController.play_file` and Admin Sounds are untouched. `tests/test_alert_batch.py` and the Spotify pause/resume tests still cover alert playback.

## Left in place on purpose

- LED `rainbow_pulse` and matrix `rainbow_pulse` (plus `hsv_to_rgb`, now in `led_controller.py`) have no caller now. They were left alone to keep the change off the LED and matrix code. Remove them in a separate change if wanted.
- `SpotifyController.is_online` and `online_cached` are still used by the Spotify code itself.
- Old DB rows `music_break_config` and `music_break_fired` in `app_settings` are harmless and not migrated.
