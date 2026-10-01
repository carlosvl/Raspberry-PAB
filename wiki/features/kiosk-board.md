---
title: Kiosk board display
type: feature
sources:
  - web/js/kiosk.js
  - web/sw.js
  - web/css/kiosk.css
  - src/raspberry_pab/race_results/team_standings_live.py
  - src/raspberry_pab/race_results/team_standings_scheduler.py
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

## Team-competition strip

The bottom strip (`#kioskTicker` / `#kioskTeams`) replaced the tiny sideways marquee (2026-09-29, branch `feature/board-team-strip`). `renderTeamTicker` in `kiosk.js` reads `buckets[]` from `/api/team-standings` (not `ticker_text`, which the matrix and admin still use). It shows **every race day with results** (2026-09-30), current day first then newest past races, one large card at a time, rotating every 6 s: "High School D1" / "Middle School D2" plus the race date (e.g. "Sun, Sep 27", from `race_date`), then chips for places 1-3 (`#n school points`). The focus team (Roseville) is a solid accent chip. If it is outside the top 3, a highlighted chip is appended after "…". The strip is rebuilt only when the data changes, so the 30 s poll doesn't restart the rotation. Cards for the board's date (`displayDate`, sim-clock aware) are accent-colored with a "Today" tag; other days use `--board-past` (violet, orange on the daylight theme) with a "Past race" tag. Chips shrink with "…" if a row is too wide, but the focus chip never shrinks, and a trailing " HS"/" MS" is dropped from school names (the card title already says the level). Found on the Pi (board font scale 1.3, long real names): before this, the Roseville chip ended at x=2449 on a 1920 px screen, i.e. off-screen. **The LED matrix only shows the current race day**: the scheduler filters with `format_matrix_messages(..., on_date=effective_now(store).date())`, so on a day without results nothing scrolls. `matrix_messages` in the API still lists all days. Roku is unchanged.

Testing note: a browser pane that visited localhost earlier runs a **service worker**, and it can serve old CSS/JS. Unregister it and clear `caches` before judging a change.

## Stale JS after deploys

`web/sw.js` fetches `/`, `/admin` and the JS network-first. Static files have no cache headers, so before 2026-09-29 the network-first `fetch()` could still be answered from the browser HTTP cache with an **old `kiosk.js` after a deploy**. It now uses `cache: "no-cache"` (revalidate, a cheap 304), and the cache name was bumped to v67. After a deploy, the first load installs the new worker and the **second** load runs the new JS, so reload the kiosk display twice.

The service worker only helps `http://localhost` and https origins. On the LAN address (`http://192.168.4.64:8080`), browsers run **no service worker** because it isn't a secure context. There, the old `kiosk.js` came straight from the HTTP cache (0 bytes transferred), and two normal reloads still ran the old code (user, 2026-09-29).

Fix (2026-09-29): `server.py` sends `Cache-Control: no-cache` on `/`, `/admin`, `/sw.js` and everything under `/css`, `/js` and `/assets` (`RevalidatingStaticFiles`). Browsers revalidate via ETag, so an unchanged file is a cheap 304. A browser that cached a file **before** this header shipped keeps it until its heuristic expiry, so do one hard refresh (Cmd+Shift+R) per device, once.
