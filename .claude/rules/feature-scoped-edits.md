# Feature-scoped changes only

When implementing or fixing something, **only edit code that belongs to that feature**. Do not “drive-by” refactor, tidy, or “improve” unrelated modules.

## Do

- Touch the smallest set of files needed for the stated task
- Prefer additive changes over rewriting shared helpers used by other features
- If a shared path (e.g. `server.py`, `sound_controller.py`, Admin `loadAll`) must change, keep the diff limited to the new wiring

## Do not (without asking first)

- Change behavior of unrelated features while working on another
- Expand scope to “while we’re here” cleanups, renames, or API reshuffles
- Alter LED / matrix / buzzer / Wi‑Fi / Roku / schedule / branding / Bluetooth (etc.) unless the user asked for that feature
- Fix adjacent bugs you notice in passing — **stop and ask** before editing

## If scope is unclear or wider than expected

1. Pause
2. Tell the user what else would need to change and why
3. Wait for confirmation before editing those files

## Examples

```text
✅ Task: Bluetooth connect busy error
   Edit: manage-pi-bluetooth.sh, maybe bluetooth route tests
   Do not: restyle Admin Sounds, change music-break scheduler

❌ Task: Music break LED not lighting
   Also rewrite matrix rainbow + sound sink resolver “for consistency”
   → Ask first; only touch LED settings persistence unless approved
```
