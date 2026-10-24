---
title: State qualification what-if
type: feature
sources:
  - src/raspberry_pab/race_results/state_whatif.py
  - scripts/mca-state-whatif.py
  - .claude/skills/mca-state-whatif/SKILL.md
  - tests/test_mca_state_whatif.py
  - user (2026-10-05)
updated: 2026-10-06
---

# State qualification what-if

Answers "would this athlete have made State in another category?" Entry
point: the `/mca-state-whatif` skill, which runs `scripts/mca-state-whatif.py`
and writes `docs/mca-state-whatif.md`. It reuses the
[qualification](state-qualification.md) pipeline (`load_season` in
`scripts/mca-state-qualification.py`), so the baseline is exactly the
qualification report.

## Method (`move_category`)

- For each race the athlete **finished**, take their IYR time in the old
  category × (new / old race distance) × fatigue, and slot it into the new
  category's real finishing order (IYR finishers, DNFs excluded).
- **Distance ratio:** from IYR `total_distance` of each category's winner
  (Xcel: 9.75 → 13.0 mi = 4/3). Cuyuna 2026 reports one 3.75 mi lap for
  every category, so it borrows the average ratio of the athlete's other
  races; `--distance-ratio` overrides all.
- **Everyone else is re-scored:** riders at or behind the inserted place in
  the new category drop one place; riders behind the athlete in the old
  category move up one. Places are recovered from points by inverting the
  [Appendix A](../concepts/mca-regulations.md) grid; a non-grid value is left
  alone.
- Missed races and DNFs stay 0. Ranking/qualification then uses `evaluate`
  unchanged (qualifies = rank ≤ 100 and ≥ 2 starts).
- **Race → IYR map:** standings columns (2, 3A, …) need `--race LABEL=ID`
  from the [season page](../races/mca-2026-season.md); merged races are
  mapped automatically.

## Results

- **2026-10-05, Carlos Mateo Villalpando JV3 Boys → Varsity Boys:** would
  have finished 54/56, last (37) and last (51) — but Varsity points for those
  places (357, 383, 361) beat his JV3 points (314, 302, 312). Avg 367.0,
  #79/104 → qualifies (actual #128/196 JV3, out). Same answer at 5% and 10%
  fatigue. Nobody else crosses the line; fewer than 100 Varsity Boys had 2+
  starts, so any 2-race Varsity rider was in. Roseville 20 → 21.
- **2026-10-06 rerun on official through-Race-6 standings** (Cuyuna is column
  `6`, so pass `--race 6=17335`): same answer, #79/104, avg 367.0 (actual now
  #127/196 JV3). Standings rows have no plate any more, so `find_row` matches
  the IYR row by name.

## Limits

- Pace held over the longer race is optimistic; use the fatigue rows.
- IYR places can differ slightly from official ones (DNFs, penalties).
