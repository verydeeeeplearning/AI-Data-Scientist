"""Helpers to summarize SQL query results for LLM-friendly payloads."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from uuid import uuid4

_DEFAULT_PREVIEW_ROWS = 20
_DEFAULT_PERSIST_THRESHOLD = 500


@dataclass(frozen=True, slots=True)
class SqlResultSummary:
    """Normalized SQL result payload components."""

    columns: list[str]
    data: list[list[object | None]]
    row_count: int
    summary_stats: dict[str, dict[str, object]]
    truncated: bool
    saved_result_path: str | None = None


def summarize_sql_rows(
    rows: list[dict],
    *,
    workspace_dir: Path | None = None,
    preview_rows: int = _DEFAULT_PREVIEW_ROWS,
    persist_threshold: int = _DEFAULT_PERSIST_THRESHOLD,
) -> SqlResultSummary:
    """Summarize result rows and optionally persist large outputs to CSV."""
    columns = _collect_columns(rows)
    preview = [_row_to_values(row, columns) for row in rows[:preview_rows]]
    summary_stats = {
        column: _summarize_column([row.get(column) for row in rows])
        for column in columns
    }
    saved_result_path: str | None = None

    if len(rows) > persist_threshold and workspace_dir is not None:
        saved_result_path = _persist_rows(rows, columns, workspace_dir)

    return SqlResultSummary(
        columns=columns,
        data=preview,
        row_count=len(rows),
        summary_stats=summary_stats,
        truncated=len(rows) > preview_rows,
        saved_result_path=saved_result_path,
    )


def _collect_columns(rows: list[dict]) -> list[str]:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for column in row:
            if column not in seen:
                seen.add(column)
                columns.append(column)
    return columns


def _row_to_values(row: dict, columns: list[str]) -> list[object | None]:
    return [row.get(column) for column in columns]


def _summarize_column(values: list[object | None]) -> dict[str, object]:
    nulls = sum(1 for value in values if _is_null(value))
    non_null = [value for value in values if not _is_null(value)]

    if not non_null:
        return {
            "type": "unknown",
            "nulls": nulls,
            "unique": 0,
        }

    summary: dict[str, object] = {
        "type": _infer_type(non_null),
        "nulls": nulls,
        "unique": len({_normalize_hashable(value) for value in non_null}),
    }

    if _is_numeric_sequence(non_null):
        numbers = [float(value) for value in non_null]  # type: ignore[arg-type]
        summary["min"] = min(non_null)  # type: ignore[type-var]
        summary["max"] = max(non_null)  # type: ignore[type-var]
        summary["mean"] = sum(numbers) / len(numbers)
        return summary

    if _is_temporal_sequence(non_null):
        ordered = sorted(non_null)  # type: ignore[type-var]
        summary["min"] = ordered[0]
        summary["max"] = ordered[-1]

    counter = Counter(_normalize_hashable(value) for value in non_null)
    summary["top_values"] = [
        {"value": value, "count": count}
        for value, count in counter.most_common(5)
    ]
    return summary


def _infer_type(values: list[object]) -> str:
    if _is_numeric_sequence(values):
        if any(isinstance(value, float) for value in values):
            return "float"
        return "integer"
    if all(isinstance(value, bool) for value in values):
        return "boolean"
    if _is_temporal_sequence(values):
        return "datetime"
    type_names = {type(value).__name__ for value in values}
    if len(type_names) == 1:
        return next(iter(type_names))
    return "mixed"


def _is_numeric_sequence(values: list[object]) -> bool:
    return all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values)


def _is_temporal_sequence(values: list[object]) -> bool:
    return all(isinstance(value, (datetime, date, time)) for value in values)


def _is_null(value: object | None) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _normalize_hashable(value: object) -> object:
    try:
        hash(value)
    except TypeError:
        return json.dumps(value, default=str, sort_keys=True)
    return value


def _persist_rows(rows: list[dict], columns: list[str], workspace_dir: Path) -> str:
    output_dir = workspace_dir / "artifacts" / "sql"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"query_result_{uuid4().hex[:12]}.csv"

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in columns})

    return str(output_path)
