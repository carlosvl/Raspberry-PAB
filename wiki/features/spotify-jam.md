---
title: Spotify Jam QR
type: feature
sources:
  - src/raspberry_pab/spotify_jam.py
  - src/raspberry_pab/routes/spotify.py
  - web/js/kiosk.js
  - web/js/admin.js
  - docs/spotify.md
  - user (2026-10-02)
updated: 2026-10-02
---

# Spotify Jam QR

The board can show a QR so guests join a Spotify Jam and add songs. How-to: [docs/spotify.md](../../docs/spotify.md).

- **No Jam detection.** Spotify's public Web API has no Jam feature, and go-librespot (the Pi's Connect receiver) doesn't report one. The admin pastes the Jam share link (Spotify app: Invite, Copy link) in Admin, Spotify, **Jam QR**, and taps Show or Hide (user, 2026-10-02).
- **Storage:** `app_settings` key `spotify_jam_url`. Empty means hidden. `normalize_jam_url` only accepts `https` links on `spotify.com`, `spotify.link` or `spotify.app.link` (the board is public, so no arbitrary QR targets).
- **API:** `GET /api/spotify/jam` is public and read-only and returns `{active, url, svg}`. `GET`, `PUT` and `DELETE /api/admin/spotify/jam` need the admin PIN.
- **QR:** made server-side by `segno` as an inline SVG with a `viewBox`, so CSS scales it. `segno` is a new runtime dependency, so the Pi needs `pip install segno` once.
- **Board:** `kiosk.js` polls every 10 s into `#jamPanel`, a white card in `.kiosk__footer` beside the team strip. While it shows, the footer gets `kiosk__footer--jam`, which makes team chips smaller so long school names still fit beside the QR (see [kiosk board](kiosk-board.md)).
- **Verified (2026-10-02):** Chromium's `BarcodeDetector` decoded the rendered QR to the exact link. A real phone scan is still the user's check.
