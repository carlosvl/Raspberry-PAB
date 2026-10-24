---
name: mca-state-whatif
description: >-
  What-if scenarios for MCA State qualification: re-score one athlete as if
  they had raced a different category all season (e.g. Varsity instead of
  JV3) and show how the qualifier list changes. Use when the user asks "what
  if X had raced Varsity/JV2/JV3", "would X have made state in another
  category", or wants to compare categories for an athlete.
argument-hint: "<athlete> <new category> [team]"
---

# MCA State qualification what-if

Builds on the `mca-state-qualification` skill (same standings + merged races).
Read `wiki/features/state-whatif.md` first (wiki rule).

## Inputs

| Input | Default |
|-------|---------|
| Athlete | required (name as in the standings; partial names match) |
| New category | required, MCA spelling: `Varsity Boys`, `JV3 Boys`, `JV2 Boys D2`, … |
| Team | `Roseville` |
| Fatigue | `1.0, 1.05, 1.10` (first = headline) |

## Steps

1. Map every standings race column the athlete raced to its IYR series id
   from the table in `wiki/races/mca-2026-season.md` (e.g. 2026 Roseville:
   `2=17319`, `3A=17320`). Races merged after the snapshot (Cuyuna) are mapped
   automatically.
2. Run from the repo root (needs network to ITS YOUR RACE and MCA; same
   flags as the qualification skill):

   ```bash
   .venv/bin/python scripts/mca-state-whatif.py \
     --athlete '<NAME>' --to-category '<CATEGORY>' --team '<TEAM>' \
     --race 2=17319 --race 3A=17320 \
     --state-event 17339 --canceled 17333:HS
   ```

   - Cloudflare 403 → wait ~30 s and retry (max 2), then report. Never invent
     numbers.
   - "can't tell … distance" → IYR reports the same distance for both
     categories at every race; ask the user for the lap counts and pass
     `--distance-ratio` (e.g. `1.3333` for 3 → 4 laps).
   - "no … results for race X" → add the missing `--race X=<IYR id>`.
3. Read `docs/mca-state-whatif.md` (overwritten each run; don't commit it
   unless asked).
4. Report concisely: actual vs what-if rank/average and whether they
   qualify; the race-by-race places; the team's qualifier count before →
   after; anyone else who crosses the top-100 line; and the sensitivity row
   if fatigue changes the answer. Say it's a projection (pace held over the
   longer race, IYR times, preliminary races marked `*` in the main report).
5. Ingest: append a `query` line to `wiki/log.md` with the scenario and
   answer; run `.venv/bin/python scripts/wiki-lint.py`.
