---
name: "mca-state-whatif"
description: "Run MCA State-qualification what-ifs, such as an athlete racing another category (Varsity instead of JV3), using the Raspberry-PAB repo on Carlos's Mac."
---

# MCA State qualification what-if

The code, data cache and the full repo skill live in `~/Documents/Github/Raspberry-PAB` on Carlos's Mac:
- Script: `scripts/mca-state-whatif.py` (logic in `src/raspberry_pab/race_results/state_whatif.py`)
- Repo skill with the details: `.claude/skills/mca-state-whatif/SKILL.md`
- Method and past results: `wiki/features/state-whatif.md`
- Race -> IYR id map: `wiki/races/mca-2026-season.md`

ITS YOUR RACE and minnesotacycling.org are not reachable from cloud containers, so the script must run on the Mac. Inside that repo, follow the repo skill. From anywhere else (for example a Claude project thread), start a Remote Control session in that folder and have it run the steps below.

## Inputs
- Athlete (required) and new category in MCA spelling (`Varsity Boys`, `JV3 Boys`, `JV2 Boys D2`, ...)
- Team: default `Roseville`
- Fatigue: default 1.0, 1.05, 1.10

## Steps
1. Map each standings race the athlete raced to its IYR series id from the season page (2026 Roseville: `2=17319`, `3A=17320`). Races merged after the standings snapshot (such as Cuyuna) are mapped automatically.
2. From the repo root, run:
   `.venv/bin/python scripts/mca-state-whatif.py --athlete '<NAME>' --to-category '<CATEGORY>' --team '<TEAM>' --race 2=17319 --race 3A=17320 --state-event 17339 --canceled 17333:HS`
   - On a Cloudflare 403, wait about 30 s and retry up to 2 times, then report the failure. Never invent numbers.
   - If it says it can't tell the distances apart, ask for the lap counts and pass `--distance-ratio` (for example 1.3333 for 3 -> 4 laps).
   - If it says a race has no results, add the missing `--race LABEL=ID`.
3. Read `docs/mca-state-whatif.md`.
4. Report: actual vs what-if rank, average and whether the athlete qualifies; the race-by-race places; the team's qualifier count before and after; anyone else who crosses the top-100 line; and fatigue sensitivity when it changes the answer. Say it is a projection: pace is held over the longer race and places come from IYR times.
5. Follow the repo's wiki rule: add a `query` line to `wiki/log.md` and run `.venv/bin/python scripts/wiki-lint.py`. Don't commit unless asked.