---
name: mca-team-standings
description: >-
  Calculate MCA team standings from the latest ITS YOUR RACE results (2026 MCA
  Chapter 11 + Appendix A scoring), write docs/mca-team-results.md, and report
  the focus team's place per division. Use when the user asks for team
  standings, team scores, "how did Roseville do", or to refresh/recalculate
  team results after more categories post.
argument-hint: "[team name] [IYR series URL]"
---

# MCA team standings

Scores every team from an ITS YOUR RACE series page with the repo's own engine
(`src/raspberry_pab/race_results/mca_scoring.py`) via
`scripts/mca-team-results.py`. Background and rules: `docs/mca-team-scoring.md`.

## Inputs

Parse from the skill args, falling back to defaults:

| Input | Default |
|-------|---------|
| Team | `Roseville` (case-insensitive match) |
| Series URL | `https://www.itsyourrace.com/results.aspx?id=17320` |
| Output | `docs/mca-team-results.md` |

If the user names a different race/series without a URL, ask for the IYR
results URL rather than guessing an id.

## Steps

1. Run from the repo root (quote the URL — zsh globs `?`):

   ```bash
   PYTHONPATH=src .venv/bin/python scripts/mca-team-results.py \
     --url '<URL>' --team '<TEAM>' --out docs/mca-team-results.md
   ```

   - No `.venv`? Run `make install-dev` first (needs `curl_cffi`, `beautifulsoup4`).
   - Cloudflare `403` / timeout: wait ~30 s and retry up to 2 times, then report
     the failure. Never fall back to made-up numbers.
   - Allow a long timeout (a few minutes); it fetches every category.

2. Read the stdout summary (`Synced N categories (M skipped)` and the focus
   team's `#place score mix` lines), then read `docs/mca-team-results.md` for
   the full tables.

3. Report to the user, concise:
   - Per race date and bucket where the focus team placed: **place / total
     teams**, score, gender mix, and the gap to the team directly ahead and
     behind (and to 1st if not leading).
   - Top 3 in each bucket the focus team is in.
   - The focus team's scoring riders (from the `<team> detail` table).
   - Caveats that apply: results status (e.g. *Unofficial*), skipped
     categories still missing results, teams marked † (division inferred,
     scored with D2 caps), and that team penalties are not applied.
   - Link to `docs/mca-team-results.md`.

4. `docs/mca-team-results.md` is tracked in git. Don't commit it unless asked.

5. Ingest into the wiki (`.claude/rules/llm-wiki.md`). Update
   `wiki/races/mca-2026-season.md`: add or refresh the event row and the team's
   place and score, and mark superseded values rather than deleting them. Update
   `wiki/features/team-standings.md` if you hit new scoring quirks. Then append
   a `wiki/log.md` entry and run `.venv/bin/python scripts/wiki-lint.py`.

## Scoring rules (for sanity checks)

- Appendix A place → points (Varsity / JV3 / base columns; bonuses in grid).
- HS Division I: top 8 riders, max 6 per gender.
- HS Division II and Middle School: top 4, max 3 per gender.
- Team D1/D2 inferred from split fields (`… D1` / `… D2`); combined-only teams
  use D2 caps (†).

If the numbers look wrong, debug in `mca_scoring.py` + `tests/test_mca_scoring.py`
— but that's a code change: ask before editing (feature-scoped edits rule).

## Kiosk (optional)

The Pi computes the same standings live when Admin → Race Results → **Live team
standings** is enabled; `GET /api/team-standings` returns its snapshot. Only
query the Pi (raspberry-ssh) if the user asks to compare with the kiosk.
