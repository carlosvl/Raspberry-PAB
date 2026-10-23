# Claude account setup for Raspberry-PAB

Things that live in a Claude account rather than in this repo, saved here so they
survive a move to a new Claude account (copied 2026-10-23).

| What | Where | How to restore |
|------|-------|----------------|
| `mca-state-qualifiers` skill | [skills/mca-state-qualifiers/SKILL.md](skills/mca-state-qualifiers/SKILL.md) | Claude settings → Skills → upload the folder (zip it first) |
| `mca-state-whatif` skill | [skills/mca-state-whatif/SKILL.md](skills/mca-state-whatif/SKILL.md) | Same as above |
| Weekly CI health check | [scheduled-tasks/weekly-ci-health-check.md](scheduled-tasks/weekly-ci-health-check.md) | Ask Claude to create a scheduled task from that file |

These are the **account-level** skills, which point a Claude chat at this repo on
the Mac. The repo's own skills in `.claude/skills/` load automatically in Claude
Code and need no restoring.

## Known gap (2026-10-23)

`mca-state-whatif` refers to `scripts/mca-state-whatif.py`,
`src/raspberry_pab/race_results/state_whatif.py`,
`.claude/skills/mca-state-whatif/SKILL.md` and `wiki/features/state-whatif.md`.
None of these are on `main` in GitHub yet; they exist only in the working copy on
the Mac. Commit and push them so the skill works from anywhere.
