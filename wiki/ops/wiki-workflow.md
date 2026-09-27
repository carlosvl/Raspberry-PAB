---
title: Wiki workflow
type: ops
sources:
  - .claude/rules/llm-wiki.md
  - scripts/wiki-lint.py
  - CLAUDE.md
  - https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
updated: 2026-09-27
---

# Wiki workflow

This wiki follows Karpathy's LLM Wiki pattern. Claude maintains it as part of
every task: first it queries the index and relevant pages, then does the work,
then ingests what it learned by updating pages, the index and the log, and
finally runs the lint.

- The rules live in `.claude/rules/llm-wiki.md`, which `CLAUDE.md` imports.
- The deterministic checks run with `.venv/bin/python scripts/wiki-lint.py`.
- Raw sources (code, `docs/`, IYR pages, facts the user states) are cited, not
  copied.
- Adopted on 2026-09-27, at the user's request, as a must-do rule for every
  action.
