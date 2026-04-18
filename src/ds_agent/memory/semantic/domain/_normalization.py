"""Shared normalizers for semantic memory domain models."""

from __future__ import annotations

from collections.abc import Sequence


def normalize_string_list(values: object) -> list[str]:
    """Strip, de-duplicate, and drop empty strings while preserving order."""

    if values is None:
        return []
    if isinstance(values, str):
        items = [values]
    elif isinstance(values, Sequence) and not isinstance(values, (bytes, bytearray)):
        items = list(values)
    else:
        raise ValueError("expected a sequence of strings")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized

