# Wiki log

Append-only. Newest entries at the bottom. Heading format:
`## [YYYY-MM-DD] ingest|query|lint|decision | title`

## [2026-09-27] decision | Adopt LLM Wiki pattern as a must-do rule
- Added `.claude/rules/llm-wiki.md`, `scripts/wiki-lint.py` and `wiki/`; imported the rule from `CLAUDE.md`.
- Pages: [ops/wiki-workflow](ops/wiki-workflow.md).

## [2026-09-27] ingest | MCA team standings skill and 2026 races 1–3
- Created the `/mca-team-standings` skill and scored IYR 17319, 17320 and 17333; wrote per-event and season reports in `docs/`.
- User: the HS race on 2026-09-27 (event 17333) was canceled.
- Pages: [features/team-standings](features/team-standings.md), [races/mca-2026-season](races/mca-2026-season.md).

## [2026-09-27] decision | Collapse spotify branch into main
- Squash-merged `spotify` into main as ef62215; deleted the branch locally and on origin. This repo "collapses" branches by squashing each into one commit on main.
- CI (ruff + mypy) was already red on main before the merge; pytest passes (205). Run tests with `python -m pytest` (bare `pytest` fails to import `tests`).

## [2026-09-27] ingest | Fix CI (ruff, mypy, pytest)
- CI had been red on main since at least 2026-08-23. Fixed 57 ruff errors, 55 mypy errors and the pytest `tests` import path. Added a regression test for the matrix_effect round trip after catching a bad ruff SIM118 autofix on `sqlite3.Row`.
- Pages: [ops/ci](ops/ci.md).

## [2026-09-27] ingest | Flaky matrix music-break test on CI
- `test_rainbow_pulse_cycles_until_stop` failed on CI 3.12: stop() cancels while the port is still closing in a thread. Made the test wait for the close; the controller race is logged as open.
- Pages: [ops/ci](ops/ci.md).
