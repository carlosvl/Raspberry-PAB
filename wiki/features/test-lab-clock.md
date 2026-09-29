---
title: Test Lab simulated clock
type: feature
sources:
  - src/raspberry_pab/kiosk_clock.py
  - src/raspberry_pab/routes/kiosk_clock.py
  - src/raspberry_pab/test_scenarios.py
  - web/js/admin.js
  - data/test_scenarios/austin-2025-roseville.json
  - user (2026-09-29)
updated: 2026-09-29
---

# Test Lab simulated clock

Admin → Test Lab → Simulated Clock sets a fake "now" for the kiosk. It's stored in the `app_settings` keys `kiosk_simulated_*`. `effective_now()` feeds the scheduler, music breaks, schedule, race results and the TV board, and the board follows `display_date`. **Set Pi clock** (the system clock) clears the simulation.

## Setting the clock loads that day's data (2026-09-29, branch `feature/sim-clock-day-data`)

`PUT /api/admin/kiosk-clock` (Apply sim time / Pause clock) calls `prepare_day_data()` for the new date:

1. **No riders that day, and a saved scenario covers it** (its `saturday` or `sunday`) → seeds that scenario's riders **for that date only**. The other weekend day is never wiped.
2. **Riders exist but none have results** → `RaceResultsSync.sync_date()` fetches results online.
3. The response carries `day_data` (riders before and after, seeded scenario, sync summary, `results_error`). Admin shows it as a one-line summary.

Notes:

- A failed sync (e.g. the Pi is offline at a race) is reported in `results_error`. It doesn't fail the request, and the clock is still set.
- The first sync on a fresh DB also fetches the race index. It took about 40–60 s in local testing, and the admin shows no progress while it waits.
- Days that already have riders and results reload nothing, so the response is instant.
- If a day's riders match no results, every Apply re-syncs.
- `advance`, `DELETE` and GET never load data (`day_data` is `null`).
