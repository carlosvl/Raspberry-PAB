---
title: Claude account setup
type: ops
sources:
  - claude/README.md
  - claude/skills/mca-state-qualifiers/SKILL.md
  - claude/skills/mca-state-whatif/SKILL.md
  - claude/scheduled-tasks/weekly-ci-health-check.md
  - user (2026-10-23)
updated: 2026-10-24
---

# Claude account setup

Some of what runs this repo lives in a Claude account, not in git: two
account-level skills that point a Claude chat at the repo on the Mac, and a weekly
cloud scheduled task that checks CI. As of 2026-10-23 the user is moving to a new
Claude account, so copies are kept in [`claude/`](../../claude/README.md) to
restore from.

- **Account skills** `mca-state-qualifiers` and `mca-state-whatif` wrap the repo
  skills and scripts for use outside Claude Code. They are separate from
  `.claude/skills/`, which Claude Code loads on its own.
- **Weekly CI health check** runs Mondays 8:59 AM Central, re-runs ruff, mypy and
  pytest with the latest tools, and opens a `ci-health-fix` PR only for small fixes.
  See [CI checks](ci.md).

~~The `mca-state-whatif` account skill names `scripts/mca-state-whatif.py`
and `.claude/skills/mca-state-whatif/`, which are not on `main` as of 2026-10-23
(they exist only in the Mac working copy).~~ Committed on branch
`claude/project-thread-p93cag` with a PR to `main` (2026-10-24); on `main` once
that merges.
