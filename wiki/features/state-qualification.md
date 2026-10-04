---
title: State Championship qualification
type: feature
sources:
  - src/raspberry_pab/race_results/mca_archive.py
  - src/raspberry_pab/race_results/mca_standings.py
  - src/raspberry_pab/race_results/mca_race_pdf.py
  - src/raspberry_pab/race_results/state_qualification.py
  - scripts/mca-state-qualification.py
  - .claude/skills/mca-state-qualification/SKILL.md
  - tests/test_mca_state_qualification.py
  - https://minnesotacycling.org/results-archive/
updated: 2026-09-28
---

# State Championship qualification

This feature answers "is this athlete on track for State?" (top 100 per
category; see [regulations](../concepts/mca-regulations.md)). It checks one
athlete, or the whole team when no one is named. Entry point: the
`/mca-state-qualification` skill, which runs `scripts/mca-state-qualification.py`
and writes `docs/mca-state-qualification.md`.

## Data sources (in priority order)

1. **MCA official standings** from the
   [results archive](https://minnesotacycling.org/results-archive/), titled
   "Individual Points through Race N" (HS + MS).
   - These are MCA's own averages and ranks. Every row is validated: the
     average recomputed from the race cells must equal the season score,
     otherwise a `StandingsParseError` is raised.
   - **Race cells:** a number is points, `-` is a bye, `0` means the team
     raced but the rider didn't, and `NA (Upgrade)` marks a race before a
     category change.
   - The HS PDF has no header row, so it borrows the MS race columns.
   - **Title layout changed at Race 5 (2026-10-02):** it's now two lines, with
     "through Race N <date>" on either the title or the level line (MS and HS
     differ). The parser accepts both old and new layouts; rows were unchanged.
2. **Races after the snapshot:**
   - The official "Individual Results" PDF (Precision Race layout), matched
     by venue.
   - If none is posted, ITS YOUR RACE, marked **preliminary**. IYR bib =
     season plate, so rows join the standings by plate.
3. **The Precision Race index** lists the events and dates. Events whose
   Saturday is after the standings "as of" date get merged.
   **State Championship events are excluded** (`--state-event`).

## Merge rules for a newer race

- **Scheduled:** a team counts as scheduled if any of its riders appears at
  that race.
- **Missed:** a rider on a scheduled team who didn't race gets `0`.
- **Bye:** riders on other teams get a bye.
- **Level not held:** if a level has no results at all, it's treated as not
  held and left out of every average. For teams that were at the event
  (they appear at the other level) it still uses one of their 4 race slots
  (`✕`); for everyone else it's a bye. Example: the Theodore Wirth HS race
  canceled 2026-09-27.
- **DNF** = 0 points but counts as a start.
  - *Official PDFs* mark DNFs explicitly.
  - *IYR* shows DNFs with a place number. The shared rule
    `mca_scoring.is_dnf` counts as DNF: 0 laps, the 2:00:00 placeholder, a
    time of 10h or more, or fewer laps than the winner. On Race 2 every
    short-lap IYR row was an official DNF.

## Report display

- The Races column lists only the races a rider's team was scheduled for;
  byes are hidden, so they don't look like counted races. Each merged race
  says whether the team raced it or had a bye. Gamehaven 9/26 was a Roseville
  bye (user, 2026-09-28) and never counted in any Roseville average.

## Status and projection

- **Status:**
  - `ON TRACK`: rank < 90, or a field of 100 or fewer.
  - `BUBBLE`: rank 90–110.
  - `OFF TRACK`: rank > 110.
  - `NEEDS RACES`: fewer than 2 starts. Races before an upgrade count; a `0`
    may hide a DNF.
- **Races left:** computed per team as 4 − races scheduled so far
  (`remaining_by_team`). Every team, not just the focus team, is projected
  with its own count. `--remaining-races` overrides the focus team only.
  Caveat: if MCA shows a canceled race as `-`, that team's count is one too
  high.
- **Projection:** each rider repeats their own average finish in each of
  their team's remaining races. Then everyone is re-ranked.
- **Points needed** = (projected #100 average × (races + remaining) − total)
  ÷ remaining, converted to a place with the Appendix A grid.

## Validation (2026-09-27)

- **Ranks:** recomputed ranks equal MCA's for all 2,276 riders in the
  through-Race-4 PDFs.
- **Team scores:** the official Race 2 results PDF, fed through the team
  engine, reproduces the official MS D2 sheet (St Louis Park 1917 … Roseville
  1721 7th).

## Open

- **Plate changes ~~aren't joined~~ fixed 2026-10-04:** a rider whose IYR bib differs from the
  standings plate (Clara Walz 4568 → 3585, 6 riders at Cuyuna) is scored as
  missing the race. `merge_race` now falls back to name + team when exactly
  one standings row fits, and flags the rider.
- **Partly posted level:** if one category of a held level isn't posted yet
  (e.g. JV2 Boys D2 at Cuyuna 10/4), its riders show as missed (0) until it
  posts. Re-run after all categories are up.

- **Existing team scoring counted DNFs:** ~~open~~ fixed 2026-09-27;
  `riders_from_sessions` now drops `is_dnf` rows.
- **Undetectable DNFs:** a DNF with a full lap count and a plausible time
  (Race 2 Varsity Girls, Sydney Bullard) can't be caught from IYR data. Only
  the official PDF shows it.

Season data: [MCA 2026 season](../races/mca-2026-season.md).
