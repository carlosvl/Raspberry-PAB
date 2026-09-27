# Project wiki — MUST DO on every action

Adapted from Karpathy's LLM Wiki pattern
(<https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>).
`wiki/` is a persistent, compounding knowledge base that Claude maintains.
Knowledge is written down once and kept current; it is not re-derived from
scratch each session.

## Three layers

| Layer | What | Who edits |
|-------|------|-----------|
| **Raw sources** | Code, `docs/`, firmware, generated reports, external URLs (ITS YOUR RACE, datasheets), and facts the user states in chat | Immutable from the wiki's side: pages cite them, never copy them wholesale |
| **Wiki** | `wiki/**/*.md`: synthesized pages about features, hardware, races, ops and decisions | Claude writes; the user curates |
| **Schema** | This file + `CLAUDE.md` | Change only when the user asks |

## Every task: Query → Work → Ingest

1. **Query (before acting).** Read `wiki/index.md`, then the pages relevant to
   the task. Treat them as the starting context. If a page contradicts the code,
   the code wins: fix the page in step 3.
2. **Work.** Do the task (other rules still apply, including feature-scoped
   edits). If a tool fails or something surprises you, check the wiki for a
   known issue before debugging from scratch.
3. **Ingest (before the final reply).** For anything durable you learned or
   changed:
   - Update the relevant page(s), or create one if no page covers it
     (search the index first to avoid duplicates).
   - Add or refresh the page's line in `wiki/index.md`.
   - Append one entry to `wiki/log.md`.
   - Run `.venv/bin/python scripts/wiki-lint.py` and fix all errors.

Skip ingest only for things that aren't durable: pure questions already
answered by the wiki, typo fixes, or throwaway commands. Still append a
`query` log line when an answer was synthesized from the wiki. File genuinely
new findings as pages.

Wiki edits are always in scope. The feature-scoped-edits rule does not block
them.

## Page format

```markdown
---
title: MCA 2026 season
type: feature | hardware | race | ops | decision | concept
sources:
  - src/raspberry_pab/race_results/mca_scoring.py
  - https://www.itsyourrace.com/results.aspx?id=17319
  - user (2026-09-27)
updated: 2026-09-27
---

# MCA 2026 season

Body. Cross-link other pages with relative links: [team standings](../features/team-standings.md).
```

- `sources`: repo paths (must exist; lint checks), URLs, or `user (YYYY-MM-DD)`
  for facts stated in chat.
- `updated`: when the wiki learned it (belief time). Put *when a fact held*
  (valid time) in the text, e.g. "as of 2026-09-27 results are Unofficial".
- **Superseded, not deleted.** When a fact changes, strike it through and add
  the replacement with a date: `~~Unofficial~~ Official (2026-10-02)`.
- **Flag contradictions** inline as `> ⚠ Conflict: …` until resolved.
- Keep pages short and factual. Link to `docs/` for step-by-step how-tos; don't
  duplicate them.

## Special files

- `wiki/index.md`: catalog grouped by category. One line per page:
  `- [Title](path.md) — one-line summary`. Every page must be listed.
- `wiki/log.md`: append-only, newest at the bottom. Never rewrite past entries.
  Format:
  `## [YYYY-MM-DD] ingest|query|lint|decision | short title`, followed by
  1–3 bullets on what changed and which pages were touched.

## Lint

`scripts/wiki-lint.py` does deterministic checks: frontmatter fields, index
coverage, broken relative links, missing repo source paths (stale pages) and
log format. It exits non-zero on errors. Run it at the end of every ingest.
When the user asks for a wiki health check, also review the pages yourself for
stale claims versus current code, contradictions, orphans and gaps. Log the
result as a `lint` entry.

## Wiki vs. other memory

- `wiki/` is committed and shared with anyone who clones the repo. Project
  knowledge goes here.
- Claude's per-user auto-memory holds only personal preferences and
  machine-specific facts (e.g. the Pi's current DHCP address).
