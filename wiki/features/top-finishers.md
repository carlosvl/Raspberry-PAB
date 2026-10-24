---
title: Top finishers by category
type: feature
sources:
  - src/raspberry_pab/race_results/top_finishers.py
  - scripts/mca-top-finishers.py
  - src/raspberry_pab/race_results/team_contacts.py
  - tests/test_mca_top_finishers.py
  - https://minnesotacycling.org/team-finder-2/
  - docs/mca-top-finishers.md
  - user (2026-10-12)
updated: 2026-10-13
---

# Top finishers by category

Scouting list (requested 2026-10-12): top 15 per HS category (Freshman, JV2, JV3,
Varsity; girls and boys) with school, name, bib and search links. Run
`.venv/bin/python scripts/mca-top-finishers.py`; it writes
`docs/mca-top-finishers.md`. Flags are the state-qualification ones plus
`--top` and `--race-id` (default 17339, State at Redhead).

- **Two bases:** the State race (ITS YOUR RACE places, DNFs dropped via
  `is_dnf`; Unofficial until MCA posts the PDF) and the season standings
  (`load_season`, ranked by average, ties share a rank). The race is kept out of
  the season list.
- **D1/D2 stay separate** where MCA splits them (Freshman Boys, JV2 Boys), so
  there are 10 lists per basis. Senior Open and middle school are excluded.
- **Locating riders:** no Strava data exists in our sources. Each row has a
  Strava athlete-search link and a Google search (name + school); matching is
  manual. The bib is the season plate; plate-less standings rows get it from the
  race by name + team.
- **Team contact (2026-10-13):** `team_contacts.py` maps each result-sheet school to
  its MCA Team Finder entry (team site + the team address MCA publishes). Team level
  only, no rider/parent contacts (riders are minors; user was pointed to coaches).
  Minneapolis/St Paul city schools have no confident match and link to the Team
  Finder. Copied 2026-10-13; re-check if an address bounces.
- **V16 standings header (2026-10-12):** MCA re-posted Race 6 with the title
  "...through Race 6" (no venue) and "Middle School 10/6/2026 as of 15:00".
  `mca_standings.py` now accepts it (test in `test_mca_state_qualification.py`).

Related: [state qualification](state-qualification.md).
