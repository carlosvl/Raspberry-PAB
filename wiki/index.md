# Raspberry-PAB wiki — index

This knowledge base is maintained by Claude; the rules are in
`.claude/rules/llm-wiki.md`. Start every task here. For project layout and
commands, see `CLAUDE.md`. For step-by-step setup, see `docs/`.

## Features

- [Kiosk board display](features/kiosk-board.md) — rider table refresh, auto-scroll bounce (1x-screen freeze fix), Roku paging, service-worker stale JS
- [State Championship qualification](features/state-qualification.md) — top-100 check from MCA official standings + newer races, merge rules, projection
- [MCA team standings](features/team-standings.md) — scoring engine, skill/CLI vs. kiosk live mode, tie and † quirks, where reports go
- [Test Lab simulated clock](features/test-lab-clock.md) — fake kiosk "now"; setting it seeds the matching scenario and syncs results for that day

## Concepts

- [MCA 2026 Sporting Regulations](concepts/mca-regulations.md) — points grid, season average, State qualification, team scoring, call-ups; rainout conflict flagged

## Races

- [MCA 2026 season](races/mca-2026-season.md) — MCA↔Precision↔IYR race map, Roseville schedule, team results, State qualification snapshot

## Ops

- [CI checks](ops/ci.md) — what CI runs, tool-version parity, pytest path, sqlite3.Row `in` gotcha
- [Wiki workflow](ops/wiki-workflow.md) — how this wiki is maintained and linted
