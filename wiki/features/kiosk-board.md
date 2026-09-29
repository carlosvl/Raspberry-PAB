---
title: Kiosk board display
type: feature
sources:
  - web/js/kiosk.js
  - web/sw.js
  - src/raspberry_pab/server.py
  - roku/pab-channel/components/PabBoardScene.brs
  - user (2026-09-29)
updated: 2026-09-29
---

# Kiosk board display

The board (`/`, `web/index.html` + `web/js/kiosk.js`) re-renders the rider table every second from `/api/participants`. The Roku board (`PabBoardScene.brs`) has its own code: it **pages** 12 rows every 8 s and shows "Page x / y".

## Auto-scroll when riders overflow the screen

- `#scheduleScroll` bounces: it scrolls down at 28 px/s, pauses 2.2 s at the bottom, scrolls back up, and pauses again. Touch, wheel or pointer input pauses it for 8 s, then it continues from where the user left it.
- ~~Fixed 0.47 px step per frame, read back from `scrollTop`~~. That froze at the top on 1× screens (the Pi's TV), because Chromium rounds `scrollTop` to whole pixels, and it slowed down at low frame rates (fixed 2026-09-29, branch `fix/board-autoscroll`).
- Now a float `scrollPos` advances by elapsed time (`dt` capped at 100 ms) and is written to `scrollTop` rounded to whole pixels. The 1 s re-render restores `Math.round(scrollPos)`.
- Hidden or background tabs get no animation frames, so the list doesn't move there. That's expected, and it matters when testing in a hidden browser pane.

## Stale JS after deploys

`web/sw.js` fetches `/`, `/admin` and the JS network-first. Static files have no cache headers, so before 2026-09-29 the network-first `fetch()` could still be answered from the browser HTTP cache with an **old `kiosk.js` after a deploy**. It now uses `cache: "no-cache"` (revalidate, a cheap 304), and the cache name was bumped to v67. After a deploy, the first load installs the new worker and the **second** load runs the new JS, so reload the kiosk display twice.

The service worker only helps `http://localhost` and https origins. On the LAN address (`http://192.168.4.64:8080`), browsers run **no service worker** because it isn't a secure context. There, the old `kiosk.js` came straight from the HTTP cache (0 bytes transferred), and two normal reloads still ran the old code (user, 2026-09-29).

Fix (2026-09-29): `server.py` sends `Cache-Control: no-cache` on `/`, `/admin`, `/sw.js` and everything under `/css`, `/js` and `/assets` (`RevalidatingStaticFiles`). Browsers revalidate via ETag, so an unchanged file is a cheap 304. A browser that cached a file **before** this header shipped keeps it until its heuristic expiry, so do one hard refresh (Cmd+Shift+R) per device, once.
