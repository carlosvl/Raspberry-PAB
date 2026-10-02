# Wiki log

Append-only. Newest entries at the bottom. Heading format:
`## [YYYY-MM-DD] ingest|query|lint|decision | title`

## [2026-09-27] decision | Adopt LLM Wiki pattern as a must-do rule
- Added `.claude/rules/llm-wiki.md`, `scripts/wiki-lint.py` and `wiki/`; imported the rule from `CLAUDE.md`.
- Pages: [ops/wiki-workflow](ops/wiki-workflow.md).

## [2026-09-27] ingest | MCA team standings skill and 2026 races 1–3
- Created the `/mca-team-standings` skill and scored IYR 17319, 17320 and 17333; wrote per-event and season reports in `docs/`.
- User: the HS race on 2026-09-27 (event 17333) was canceled.
- Pages: [features/team-standings](features/team-standings.md), [races/mca-2026-season](races/mca-2026-season.md).

## [2026-09-27] decision | Collapse spotify branch into main
- Squash-merged `spotify` into main as ef62215; deleted the branch locally and on origin. This repo "collapses" branches by squashing each into one commit on main.
- CI (ruff + mypy) was already red on main before the merge; pytest passes (205). Run tests with `python -m pytest` (bare `pytest` fails to import `tests`).

## [2026-09-27] ingest | Fix CI (ruff, mypy, pytest)
- CI had been red on main since at least 2026-08-23. Fixed 57 ruff errors, 55 mypy errors and the pytest `tests` import path. Added a regression test for the matrix_effect round trip after catching a bad ruff SIM118 autofix on `sqlite3.Row`.
- Pages: [ops/ci](ops/ci.md).

## [2026-09-27] ingest | Flaky matrix music-break test on CI
- `test_rainbow_pulse_cycles_until_stop` failed on CI 3.12: stop() cancels while the port is still closing in a thread. Made the test wait for the close; the controller race is logged as open.
- Pages: [ops/ci](ops/ci.md).

## [2026-09-27] ingest | Matrix port leak on cancel (CI flake root cause)
- Root cause: a queued `to_thread` close cancelled by `stop()` never runs. Added `_close_session_port` (shield + wait) in matrix_controller and reverted the test workaround.
- Pages: [ops/ci](ops/ci.md).

## [2026-09-27] ingest | 2026 Sporting Regulations + State qualification skill
- Ingested `docs/reference/2026-MCA-Sporting-Regulations.pdf` into a concepts page, flagging the rainout contradiction between p. 19 and p. 21.
- Built `/mca-state-qualification` from MCA's official "through Race 4" standings plus preliminary Gamehaven/Theodore results. Ranks match MCA for all 2,276 riders, and Race 2 MS D2 team scores match the official sheet.
- User: Redhead (IYR 17339) is the State Championship; Roseville has 1 regular-season race left (Cuyuna). Fixed ~~17319 = Race 1~~ → MCA Race 2.
- Pages: [concepts/mca-regulations](concepts/mca-regulations.md), [features/state-qualification](features/state-qualification.md), [races/mca-2026-season](races/mca-2026-season.md), [features/team-standings](features/team-standings.md).

## [2026-09-27] ingest | DNF scoring fix + 4-race cap
- Team scoring now drops IYR DNF rows (`is_dnf`). Race 2 HS D1 now matches the official sheet: Shakopee ~~3430, 6th~~ → 3328, 7th.
- User: each team/racer does at most 4 regular-season races. Races left are now computed per team (Roseville: 1), and every team is projected with its own count.
- Pages: [features/team-standings](features/team-standings.md), [features/state-qualification](features/state-qualification.md), [concepts/mca-regulations](concepts/mca-regulations.md), [races/mca-2026-season](races/mca-2026-season.md).

## [2026-09-27] decision | Confirmed Roseville schedule and cancellation math
- User confirmed Roseville's 4 races: Xcel, Lake Rebecca, Theodore Wirth (HS canceled), Cuyuna. Added `--canceled IYR:LEVEL` to separate confirmed cancellations from results not posted yet, and a "How canceled races count" section to the report.
- Pages: [races/mca-2026-season](races/mca-2026-season.md), [concepts/mca-regulations](concepts/mca-regulations.md).

## [2026-09-28] query | Gamehaven looked counted in the qualification report
- User thought Gamehaven was counted for Roseville. It wasn't: every Roseville cell there was a bye, left out of the averages. Only the display was misleading.
- The report now hides bye cells and marks each merged race as raced or bye for the team. Pages: [features/state-qualification](features/state-qualification.md).

## [2026-09-29] ingest | Deployed latest code to kiosk Pi

- Pi (now 192.168.4.64) was on the 2026-09-25 build; rsynced 98 tracked files (HEAD 05258c7 + uncommitted state-qualification edits), restarted `raspberry-pab`, reloaded the display. Backup: `~/Raspberry-PAB-backup-20260929-081023.tgz`.
- The service imports from `src/` via `PYTHONPATH` (the venv install is not editable), so rsync plus a restart is enough. `pypdf` is dev-only and not needed on the Pi.
- The Pi repo root still has stale Sep 11 copies of `web/` and `roku/` files (`admin.html`, `js/`, `pab-channel/`, …). They are left in place until the user decides.

## [2026-09-29] ingest | Removed stale root copies on kiosk Pi
- User deleted the Sep 11 root-level copies (`admin.html`, `index.html`, `sw.js`, `manifest.webmanifest`, `kiosk.md`, `roku.md`, `css/`, `js/`, `assets/`, `pab-channel/`) from `~/Raspberry-PAB` on the Pi. The board and admin still serve from `web/` (all 200). The files are kept in `~/Raspberry-PAB-backup-20260929-081023.tgz`.

## [2026-09-29] ingest | Simulated clock loads that day's data
- On branch `feature/sim-clock-day-data`, `PUT /api/admin/kiosk-clock` now seeds riders from a matching test scenario (that date only) and syncs results when they are missing, then reports it as `day_data`. Verified in the browser: Austin 2025-08-23 seeded 8 riders and matched 6/8 results, a repeat Apply loaded nothing, and 2031-01-01 reported nothing to load.
- Pages: [features/test-lab-clock](features/test-lab-clock.md) (new).

## [2026-09-29] ingest | Deployed sim-clock day data to kiosk Pi
- Committed `fa5f2e0` on `feature/sim-clock-day-data` (not pushed to GitHub), then rsynced it to the Pi, restarted `raspberry-pab` and reloaded the display. Board and admin return 200, and the API lists `KioskDayData`. Backup: `~/Raspberry-PAB-backup-20260929-094912.tgz`. Pages: [features/test-lab-clock](features/test-lab-clock.md).

## [2026-09-29] ingest | Board auto-scroll froze on 1x screens
- The user reported the rider list never scrolls. Cause: a 0.47 px step per frame read back from `scrollTop` rounds to 0 on 1x displays. It now uses a time-based float position written as whole pixels. Also found that `sw.js` network-first fetches could return an old `kiosk.js` from the HTTP cache, so it now uses `cache: "no-cache"` (v67).
- Pages: [features/kiosk-board](features/kiosk-board.md) (new).

## [2026-09-29] ingest | Deployed board auto-scroll fix to kiosk Pi
- Copied only `web/js/kiosk.js` and `web/sw.js` to the Pi, so the sim-clock branch it runs stays intact. Reloaded the display twice, and both loads fetched `kiosk.js` fresh (200). Backup: `~/Raspberry-PAB-web-backup-20260929-103956.tgz`. Pages: [features/kiosk-board](features/kiosk-board.md).

## [2026-09-29] ingest | Remote browsers kept the old kiosk.js
- The user reloaded `http://192.168.4.64:8080/` twice and still had no scroll. The page ran the old `kiosk.js` from the HTTP cache, and no service worker runs on a plain-http LAN origin. `server.py` now sends `Cache-Control: no-cache` for UI files. Pages: [features/kiosk-board](features/kiosk-board.md).

## [2026-09-29] ingest | Deployed no-cache headers to kiosk Pi
- Copied only `server.py` (it matches the sim-clock branch the Pi runs) and restarted. `/js/kiosk.js` now returns `cache-control: no-cache`. After one cache-bypassing load, reloads revalidate (about 300 B transferred) and run the new `kiosk.js`. Backup: `~/Raspberry-PAB-server-backup-20260929-120859.tgz`.

## [2026-09-29] ingest | User confirmed the board scrolls
- After one hard refresh, the user saw the rider list scrolling on `http://192.168.4.64:8080/`. Pages: [features/kiosk-board](features/kiosk-board.md).

## [2026-09-29] ingest | Board team-competition strip
- Replaced the small marquee with large rotating division cards (top 3 + highlighted Roseville chip), frontend only (`kiosk.js`, `kiosk.css`, `index.html`, sw cache v68). Not yet deployed to the Pi. Pages: [features/kiosk-board](features/kiosk-board.md).

## [2026-09-30] ingest | Race date on team strip
- Each team card heading now shows the race date (`teamRaceDate` in `kiosk.js`, parsed as a local date so it doesn't shift a day). sw cache v69. Not yet deployed to the Pi. Pages: [features/kiosk-board](features/kiosk-board.md).

## [2026-09-30] ingest | Deployed team strip date to kiosk Pi
- Copied `kiosk.js`, `kiosk.css`, `sw.js` (v69) to the Pi at 192.168.4.64; served copies match. Backup: `~/Raspberry-PAB-web-backup-20260930-090813.tgz`. Pages: [features/kiosk-board](features/kiosk-board.md).

## [2026-09-30] ingest | Team strip shows all race days; matrix current day only
- Board shows every race day with two colors (today vs past) plus text tags; matrix scrolls only the current race day (`on_date` filter, test added). sw cache v70. Not yet deployed. Pages: [features/kiosk-board](features/kiosk-board.md).

## [2026-09-30] ingest | Deployed all-days strip + matrix filter to kiosk Pi
- Copied web (`kiosk.js`, `kiosk.css`, `sw.js` v70) and `team_standings_live.py` / `team_standings_scheduler.py` (both matched HEAD beforehand), then restarted `raspberry-pab`. Backup: `~/Raspberry-PAB-deploy-backup-20260930-092637.tgz`. The Pi runs a simulated clock (kiosk date 2026-09-25), so "today" there follows that date. After a restart the standings snapshot is empty until the first poll completes. Pages: [features/kiosk-board](features/kiosk-board.md).

## [2026-09-30] ingest | Set Pi sim clock to 2026-09-13; fixed chip overflow
- Set the Pi's simulated clock to 2026-09-13 09:00 (paused) via `PUT /api/admin/kiosk-clock`; it was 2026-09-26 running. The board showed High School cards as Today and Middle School (Sep 12) as Past race. Real names overflowed, so chips now shrink, the focus chip is fixed, and " HS"/" MS" is dropped (sw v71). Not yet deployed. Pages: [features/kiosk-board](features/kiosk-board.md), [features/test-lab-clock](features/test-lab-clock.md).

## [2026-09-30] ingest | Deployed chip-overflow fix to kiosk Pi
- Pushed `bc79e02` to PR #3 and copied `kiosk.css`, `kiosk.js`, `sw.js` (v71) to the Pi; served copies match. Backup: `~/Raspberry-PAB-web-backup-20260930-231508.tgz`. On the live page (sim clock 2026-09-13) no school names are cut and the focus chip ends at x=1838 of 1920. The Pi clock is still simulated at 2026-09-13. Pages: [features/kiosk-board](features/kiosk-board.md).

## [2026-10-02] ingest | Spotify Jam QR on the board
- Branch `feature/spotify-enhancements`. Spotify has no Jam API, so the admin pastes the link; the board shows its QR beside the team strip (`spotify_jam.py`, routes, admin card, `kiosk.js`). New dependency `segno`. Pages: [features/spotify-jam](features/spotify-jam.md), [features/kiosk-board](features/kiosk-board.md).
