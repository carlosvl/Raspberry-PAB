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

## [2026-09-29] ingest | Board auto-scroll froze on 1x screens
- The user reported the rider list never scrolls. Cause: a 0.47 px step per frame read back from `scrollTop` rounds to 0 on 1x displays. It now uses a time-based float position written as whole pixels. Also found that `sw.js` network-first fetches could return an old `kiosk.js` from the HTTP cache, so it now uses `cache: "no-cache"` (v67).
- Pages: [features/kiosk-board](features/kiosk-board.md) (new).

## [2026-09-29] ingest | Deployed board auto-scroll fix to kiosk Pi
- Copied only `web/js/kiosk.js` and `web/sw.js` to the Pi, so the sim-clock branch it runs stays intact. Reloaded the display twice, and both loads fetched `kiosk.js` fresh (200). Backup: `~/Raspberry-PAB-web-backup-20260929-103956.tgz`. Pages: [features/kiosk-board](features/kiosk-board.md).

## [2026-09-29] ingest | Remote browsers kept the old kiosk.js
- The user reloaded `http://192.168.4.64:8080/` twice and still had no scroll. The page ran the old `kiosk.js` from the HTTP cache, and no service worker runs on a plain-http LAN origin. `server.py` now sends `Cache-Control: no-cache` for UI files. Pages: [features/kiosk-board](features/kiosk-board.md).
