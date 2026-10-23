# Weekly CI health check (Claude scheduled task)

A Claude scheduled task that checks this repo's CI every week. Copied from the
old Claude account on 2026-10-23 so it can be recreated in the new one.

| Setting | Value |
|---------|-------|
| Name | Weekly CI health check |
| Schedule | Mondays at 8:59 AM, America/Chicago (`CRON_TZ=America/Chicago 59 8 * * 1`) |
| Runs | In the cloud (does not need the Mac) |
| Reports to | A Claude channel thread, only when something fails |

## Prompt

Paste this as the task's prompt:

```text
Routine: weekly CI health check. Check the latest CI run on main of carlosvl/Raspberry-PAB on GitHub. Then on a fresh checkout of main, with the latest ruff and mypy (pip install -e ".[dev]" && pip install -U ruff mypy), run ruff check src tests, mypy and pytest to catch breakage from new tool releases. If all pass, end silently. If something fails, find the cause; if the fix is small and only touches what broke, commit it on branch ci-health-fix and open a PR to main, following CLAUDE.md and the wiki rules (wiki/ops/ci.md plus log). Never deploy to the Pi. Reply in the thread only when something failed, saying what failed and what you did.
```

## Recreating it

In the new account, ask Claude: "Create a scheduled task from
`claude/scheduled-tasks/weekly-ci-health-check.md` in carlosvl/Raspberry-PAB."
The new account needs GitHub connected with access to this repo first.
