---
title: CI checks
type: ops
sources:
  - .github/workflows/ci.yml
  - pyproject.toml
  - src/raspberry_pab/db.py
  - tests/test_db.py
  - tests/test_matrix_controller.py
  - src/raspberry_pab/matrix_controller.py
updated: 2026-09-27
---

# CI checks

`.github/workflows/ci.yml` runs on every push/PR to `main` with Python
3.11–3.13. After `pip install -e ".[dev]"` it runs three steps, and all of them
must pass:

- `ruff check src tests`
- `mypy`, which uses `[tool.mypy]` in `pyproject.toml`: strict, package
  `raspberry_pab`, tests not checked
- `pytest --cov=raspberry_pab`

## History

- **Red on main** from at least 2026-08-23 until 2026-09-27: 57 ruff errors,
  55 mypy errors, and a pytest import error. All fixed on 2026-09-27.

## Gotchas

- **Tests import `tests.race_results_helpers`**, so `pytest` needs the repo
  root on its path: `pythonpath = ["src", "."]`. Before that fix, only
  `python -m pytest` worked.
- **Match CI's tool versions.** CI installs the latest ruff/mypy (2026-09-27:
  ruff 0.16.8, mypy 2.3.1). An older local venv can disagree. Upgrade with
  `.venv/bin/pip install -U ruff mypy`.
- **Don't blindly apply ruff SIM118 to `sqlite3.Row`.** `"col" in row` checks
  *values*, not column names. Keep `row.keys()` with
  `# noqa: SIM118`. `tests/test_db.py::test_rule_matrix_effect_round_trip`
  guards this. An unsafe-fix pass once silently turned every rule's matrix
  effect into `solid`.
- **zsh doesn't word-split `$VAR`.** Pipe file lists through `xargs` when
  passing them to ruff.
- **Serial ports are typed as the `SerialPort` protocol**
  (`arduino_serial.py`). pyserial is untyped, so assign `serial.Serial(...)`
  to an annotated variable before returning it.
- **Matrix port close must survive cancellation.** ~~Known race, still open;
  the test waits 2 s for the close~~ Fixed on 2026-09-27. If `stop()` cancels
  a music-break or scroll-once task while its `finally` closes the port, and
  the `asyncio.to_thread` close is still queued in the executor, cancelling
  drops the close entirely, so the serial port is leaked. It showed up as
  `test_rainbow_pulse_cycles_until_stop` failing on CI 3.11 and 3.12.
  `MatrixController._close_session_port` shields the close and waits for it
  before re-raising. Apply the same pattern to any `finally: await
  asyncio.to_thread(close)`.
