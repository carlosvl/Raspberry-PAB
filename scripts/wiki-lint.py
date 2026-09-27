#!/usr/bin/env python3
"""Deterministic health checks for the project wiki (see .claude/rules/llm-wiki.md)."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WIKI = REPO_ROOT / "wiki"
SPECIAL = {"index.md", "log.md"}
REQUIRED = ("title", "type", "sources", "updated")
TYPES = {"feature", "hardware", "race", "ops", "decision", "concept"}
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
LOG_HEADING = re.compile(
    r"^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|decision) \| \S.*$"
)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_frontmatter(text: str) -> dict[str, str | list[str]] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    data: dict[str, str | list[str]] = {}
    key = ""
    for line in text[4:end].splitlines():
        if line.startswith("  - ") and key:
            current = data.get(key)
            items = current if isinstance(current, list) else []
            items.append(line[4:].strip())
            data[key] = items
        elif ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            data[key] = value.strip() if value.strip() else []
    return data


def check_links(path: Path, text: str, errors: list[str]) -> None:
    for target in LINK.findall(text):
        if "://" in target or target.startswith(("#", "mailto:")):
            continue
        file_part = target.split("#", 1)[0]
        if file_part and not (path.parent / file_part).exists():
            errors.append(f"{path.relative_to(REPO_ROOT)}: broken link {target}")


def check_page(path: Path, errors: list[str]) -> None:
    rel = path.relative_to(REPO_ROOT)
    text = path.read_text(encoding="utf-8")
    meta = parse_frontmatter(text)
    if meta is None:
        errors.append(f"{rel}: missing frontmatter")
        return
    for field in REQUIRED:
        if not meta.get(field):
            errors.append(f"{rel}: frontmatter missing '{field}'")
    if meta.get("type") and meta["type"] not in TYPES:
        errors.append(f"{rel}: unknown type {meta['type']!r}")
    updated = meta.get("updated")
    if isinstance(updated, str) and updated and not DATE.match(updated):
        errors.append(f"{rel}: 'updated' must be YYYY-MM-DD")
    sources = meta.get("sources")
    for source in sources if isinstance(sources, list) else []:
        if "://" in source or source.startswith("user"):
            continue
        if not (REPO_ROOT / source).exists():
            errors.append(f"{rel}: stale source (missing path) {source}")
    check_links(path, text, errors)


def main() -> int:
    errors: list[str] = []
    index = WIKI / "index.md"
    log = WIKI / "log.md"
    for special in (index, log):
        if not special.exists():
            errors.append(f"missing {special.relative_to(REPO_ROOT)}")

    pages = sorted(
        p for p in WIKI.rglob("*.md") if p.relative_to(WIKI).as_posix() not in SPECIAL
    )
    for page in pages:
        check_page(page, errors)

    if index.exists():
        index_text = index.read_text(encoding="utf-8")
        check_links(index, index_text, errors)
        linked = {
            (WIKI / t.split("#", 1)[0]).resolve()
            for t in LINK.findall(index_text)
            if "://" not in t
        }
        for page in pages:
            if page.resolve() not in linked:
                errors.append(f"{page.relative_to(REPO_ROOT)}: not listed in index")

    if log.exists():
        for number, line in enumerate(
            log.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if line.startswith("## ") and not LOG_HEADING.match(line):
                errors.append(f"wiki/log.md:{number}: bad entry heading {line!r}")

    for error in errors:
        print(f"ERROR {error}")
    print(f"wiki-lint: {len(pages)} pages, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
