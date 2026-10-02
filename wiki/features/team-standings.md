---
title: MCA team standings
type: feature
sources:
  - src/raspberry_pab/race_results/mca_scoring.py
  - src/raspberry_pab/race_results/series_fetch.py
  - src/raspberry_pab/race_results/team_standings_live.py
  - scripts/mca-team-results.py
  - .claude/skills/mca-team-standings/SKILL.md
  - docs/mca-team-scoring.md
  - src/raspberry_pab/race_results/mca_race_pdf.py
updated: 2026-09-27
---

# MCA team standings

Scores every team in an ITS YOUR RACE (IYR) series using 2026 MCA Chapter 11 and
the Appendix A point grid. There are two entry points that share one engine:

- **Laptop:** the `/mca-team-standings [team] [url]` skill runs
  `scripts/mca-team-results.py` and writes a markdown report. How-to:
  [docs/mca-team-scoring.md](../../docs/mca-team-scoring.md).
- **Kiosk:** Admin → Race Results → Live team standings polls the series URL.
  The Pi exposes it at `GET /api/team-standings`, with a board ticker and a
  matrix SCROLLONCE.

## Behavior worth knowing

- **One IYR id per race weekend.** A single id can cover several dates (e.g.
  17320 = MS Sat + HS Sun). The script scores each date separately and splits
  results into HS/MS × D1/D2 buckets.
- **Ties** are ordered alphabetically (`-total_points, team_name`), so a tied
  team can print one place lower. Report ties as "T-n". Seen on 17319, where
  Roseville and Lakes Area Composite both scored 1865.
- **† teams:** the division couldn't be inferred from D1/D2 split fields, so
  they are scored with D2 caps. Which teams get † can change between scrapes as
  more results post.
- **Penalties** aren't on IYR pages and are never applied.
- **Skipped categories** means no results were posted yet. A canceled race
  also shows up as skipped; the script can't tell the difference.
- **No season aggregation.** Totals are per race only. The MCA season-points
  rule is not implemented (unknown as of 2026-09-27).
- **Results change while Unofficial.** Rescraping 17320 on 2026-09-27 shifted a
  few non-Roseville MS scores, and HS D2 went from 29 to 30 teams.

- **IYR can 403 the scraper (2026-10-02).** The live fetch uses `curl_cffi` with `impersonate=chrome131` (see `client.py`). On 2026-10-02 the Pi got **HTTP 403** with `chrome131` but **200** with `chrome124` for the same URL, and the kiosk strip stayed empty across polls (it had worked a few hours earlier). Plain `urllib` from a Mac also gets 403. Not fixed yet; changing the impersonation is a candidate fix. The board hides the strip when there are no buckets.

## Validation

- **Checked against official sheets (2026-09-27):** Race 2 HS D2 from IYR
  matches the official team-score sheet exactly, including the Roseville /
  Lakes Area Composite tie at 1865. Race 2 MS D2, built from MCA's official
  results PDF, matches as well (Roseville 1721, 7th).
- **DNFs:** ~~got points~~ fixed 2026-09-27. IYR lists DNFs with a place,
  so `is_dnf` now drops rows with 0 laps, the 2:00:00 placeholder, a 10h+
  time, or fewer laps than the winner. This corrected Race 2 HS D1: Shakopee
  went from ~~3430 (6th)~~ to **3328 (7th)** and St Paul Central to 6th,
  matching the official sheet. The kiosk live ticker uses the same path.

## Report files

- **Per event:** `docs/mca-team-results-<id>.md`.
- **Season rollup:** `docs/mca-team-results-2026-season.md`, assembled by hand
  from the per-event files.
- **Default output:** `docs/mca-team-results.md`. It is tracked in git and gets
  overwritten on every run. Pass `--out` to keep reports separate.

Season data: [MCA 2026 season](../races/mca-2026-season.md).
