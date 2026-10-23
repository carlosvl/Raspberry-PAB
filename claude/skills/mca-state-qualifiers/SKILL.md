---
name: "mca-state-qualifiers"
description: "List which Roseville (or any MCA team) athletes qualify for the MCA State Championship, using the Raspberry-PAB repo on Carlos's Mac."
---

# MCA State Championship qualifiers

The code, data cache and the full repo skill live in `~/Documents/Github/Raspberry-PAB` on Carlos's Mac:
- Script: `scripts/mca-state-qualification.py` (logic in `src/raspberry_pab/race_results/state_qualification.py`)
- Repo skill with the details: `.claude/skills/mca-state-qualification/SKILL.md`
- Rules: `wiki/features/state-qualification.md`, `wiki/concepts/mca-regulations.md`
- Season facts (state event id, cancellations, race map): `wiki/races/mca-2026-season.md`
- Projected call-ups doc: `docs/mca-state-callups.md`

Rule: the top 100 per category by season average qualify, and an athlete needs at least 2 registered races (2026 Sporting Regulations, Ch. 11).

ITS YOUR RACE and minnesotacycling.org are not reachable from cloud containers, so the script must run on the Mac. Inside that repo, follow the repo skill. From anywhere else (for example a Claude project thread), start a Remote Control session in that folder and have it run the steps below.

## Inputs
- Team: default `Roseville`
- Athletes: none means the whole team
- State event and cancellations: from the season page (2026: `--state-event 17339 --canceled 17333:HS`)

## Steps
1. From the repo root, run:
   `.venv/bin/python scripts/mca-state-qualification.py --team '<TEAM>' [--athlete '<NAME>' ...] --state-event 17339 --canceled 17333:HS --refresh`
   - `--refresh` picks up MCA PDFs that were re-posted under the same name, and official results that replace preliminary IYR ones.
   - On a Cloudflare 403, wait about 30 s and retry up to 2 times, then report the failure. Never invent numbers.
   - A `StandingsParseError` means MCA changed the PDF layout. Stop and report it.
2. Read `docs/mca-state-qualification.md`, and use `git diff` on it to see what changed since the last run.
3. Report the qualifiers grouped as middle school (Saturday) and high school (Sunday), with category, season rank/field and the call-up from `docs/mca-state-callups.md` when it is current. Then list who is not qualified and why: BUBBLE first, then fewer than 2 races, then off track. Call out changes since the last run, and note caveats such as preliminary (`*`) races or unofficial results.
4. Follow the repo's wiki rule: refresh the snapshot line in the season page, add an entry to `wiki/log.md`, and run `.venv/bin/python scripts/wiki-lint.py`. Don't commit unless asked.

For what-if scenarios, such as an athlete in another category, use the `mca-state-whatif` skill.