"""Participant name normalization and fuzzy matching."""

from __future__ import annotations

import re

_NAME_NOISE = re.compile(r"[^a-z0-9\s]", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    cleaned = _NAME_NOISE.sub(" ", name.strip().lower())
    return _WHITESPACE.sub(" ", cleaned).strip()


def name_tokens(name: str) -> list[str]:
    return [token for token in normalize_name(name).split() if token]


def names_match(participant_name: str, result_name: str) -> bool:
    left = name_tokens(participant_name)
    right = name_tokens(result_name)
    if not left or not right:
        return False
    if left == right:
        return True
    if len(left) >= 2 and len(right) >= 2:
        if left[0] == right[0] and left[-1] == right[-1]:
            left_middle = set(left[1:-1])
            right_middle = set(right[1:-1])
            if not left_middle or not right_middle or left_middle <= right_middle or right_middle <= left_middle:
                return True
    left_set = set(left)
    right_set = set(right)
    if len(left_set) >= 2 and left_set <= right_set:
        return True
    if len(right_set) >= 2 and right_set <= left_set:
        return True
    return False
