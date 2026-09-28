---
name: mca-state-qualification
description: >-
  Check whether MCA athletes are on track to qualify for the State Championship
  (top 100 per category, 2026 Sporting Regulations Ch. 11) from MCA's official
  standings plus newer race results, with a projection of points needed. Use
  when the user asks "is X going to make state", "who on the team qualifies",
  "state championship standings/cutoff", or names an athlete and state. With
  no athlete named, check every athlete on the team.
argument-hint: "[team] [athlete…]"
---

# MCA State Championship qualification

Rules, data sources and assumptions: `wiki/features/state-qualification.md`
and `wiki/concepts/mca-regulations.md`. Read those first (wiki rule).

## Inputs

| Input | Default |
|-------|---------|
| Team | `Roseville` |
| Athletes | none → **whole team** |
| Races left | computed per team: **4 regular-season races max** − races scheduled so far (a canceled race uses a slot) |
| State Championship event(s) | from `wiki/races/mca-2026-season.md` (2026: IYR `17339`, Redhead) |
| Confirmed cancellations | from the same page (2026: `17333:HS`, Theodore Wirth HS day) |

Only pass `--remaining-races N` to override the computed figure for `--team`
(e.g. a team with a schedule quirk); record why in the season page.

## Steps

1. Run from the repo root:

   ```bash
   .venv/bin/python scripts/mca-state-qualification.py \
     --team '<TEAM>' [--athlete '<NAME>' …] --state-event <IYR_ID> \
     [--canceled <IYR_ID>:HS|MS …]
   ```

   - It reads https://minnesotacycling.org/results-archive/ for the latest
     "Individual Points through Race N" HS + MS PDFs (MCA's own averages and
     ranks), then merges later races: the official Individual Results PDF if
     posted, else ITS YOUR RACE (marked preliminary `*`).
   - PDFs are cached in `~/.cache/raspberry-pab/mca/`; add `--refresh` when
     MCA re-posts a file with the same name.
   - Needs `make install-dev` (`pypdf`, `curl_cffi`). Cloudflare 403 → wait
     ~30 s and retry (max 2), then report the failure. Never invent numbers.
   - A `StandingsParseError` means MCA changed the PDF layout: stop and report
     the rows it lists; don't guess.

2. Read `docs/mca-state-qualification.md` (the report the script writes).

3. Report concisely, **BUBBLE and NEEDS RACES first**:
   - Each athlete: status, rank/field, average vs the current #100 average,
     and the projection ("needs ~X pts ≈ Nth or better at the remaining race").
   - For one named athlete, also show their per-race cells.
   - Caveats that apply: preliminary (`*`) races, results Unofficial, races
     left per team (4-race cap), `NEEDS RACES` counts finishes only (a `0` may
     be a DNF — confirm registration), grade unknown (HS seniors outside the
     top 100 can race the Senior Open), category-change flags.
   - Link the report.

4. Ingest into the wiki: refresh the standings snapshot line (which "through
   Race N" file, date) and any schedule facts in
   `wiki/races/mca-2026-season.md`; append `wiki/log.md`; run
   `.venv/bin/python scripts/wiki-lint.py`.

`docs/mca-state-qualification.md` is regenerated each run; don't commit it
unless asked.
