"""TemporalJoinGuardHook — detects future information leakage in joins.

Priority 28: runs after BaselineGuard (25) and before LeakageDetection (30).

Scans SQL queries and Python code for join/merge operations that lack
temporal conditions, which could cause look-ahead bias.
"""

from __future__ import annotations

import re

from ds_agent.agent.hooks import HookContext, PostToolUseResult, ToolHook

# Tools that might contain SQL or pandas merge code
_MONITORED_TOOLS = frozenset({
    "execute_code", "sql_query", "feature_engineer",
})

# Temporal column naming patterns
_TEMPORAL_PATTERNS = re.compile(
    r"(?:created|updated|modified|deleted|event|order|transaction|signup|login|"
    r"purchase|start|end|expire|birth|register|cancel|close|open|submit|"
    r"effective|valid)(?:_at|_date|_time|_dt|_ts)|"
    r"\btimestamp\b|\bdatetime\b|\bdate\b|\bdt\b",
    re.IGNORECASE,
)

# SQL JOIN without temporal condition
# Handles: JOIN tbl ON ..., JOIN tbl alias ON ..., JOIN tbl AS alias ON ...
_SQL_JOIN_PATTERN = re.compile(
    r"\bJOIN\b\s+(\w+)(?:\s+(?:AS\s+)?\w+)?\s+ON\s+(.+?)(?=\bJOIN\b|\bWHERE\b|\bGROUP\b|\bORDER\b|\bLIMIT\b|\bHAVING\b|;|\Z)",
    re.IGNORECASE | re.DOTALL,
)

# Python merge/join pattern
_PANDAS_MERGE_PATTERN = re.compile(
    r"\.merge\s*\(|pd\.merge\s*\(|\.join\s*\(",
    re.IGNORECASE,
)


def _has_temporal_condition(join_condition: str) -> bool:
    """Check if a JOIN condition includes a temporal comparison."""
    return bool(_TEMPORAL_PATTERNS.search(join_condition))


def _analyze_sql_joins(sql: str) -> list[dict[str, str]]:
    """Find SQL JOINs missing temporal conditions."""
    warnings: list[dict[str, str]] = []

    for match in _SQL_JOIN_PATTERN.finditer(sql):
        table = match.group(1)
        condition = match.group(2)

        if not _has_temporal_condition(condition):
            # Check if either table has temporal columns mentioned elsewhere
            warnings.append({
                "type": "sql_join",
                "table": table,
                "condition": condition.strip()[:100],
                "message": (
                    f"JOIN with '{table}' lacks temporal condition. "
                    f"If this involves time-series data, add a condition "
                    f"like 'AND events.created_at < labels.label_date' "
                    f"to prevent future information leakage."
                ),
            })

    return warnings


def _analyze_pandas_merges(code: str) -> list[dict[str, str]]:
    """Find pandas merge/join calls potentially missing temporal filters."""
    warnings: list[dict[str, str]] = []

    for match in _PANDAS_MERGE_PATTERN.finditer(code):
        # Check surrounding context (100 chars around the match)
        start = max(0, match.start() - 50)
        end = min(len(code), match.end() + 200)
        context = code[start:end]

        # Check if any temporal column is referenced near the merge
        if not _TEMPORAL_PATTERNS.search(context):
            # Extract the merge call line
            line_start = code.rfind("\n", 0, match.start()) + 1
            line_end = code.find("\n", match.end())
            if line_end == -1:
                line_end = len(code)
            merge_line = code[line_start:line_end].strip()[:120]

            warnings.append({
                "type": "pandas_merge",
                "code": merge_line,
                "message": (
                    "merge/join detected without temporal column reference. "
                    "If merging time-series data, filter by date before merge "
                    "or use merge_asof() to prevent look-ahead bias."
                ),
            })

    return warnings


class TemporalJoinGuardHook(ToolHook):
    """Warns about potential future information leakage in joins.

    Monitors SQL queries and Python code for join/merge operations
    that lack temporal conditions, which could cause look-ahead bias
    in predictive modeling.
    """

    name = "temporal_join_guard"
    priority = 28

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name not in _MONITORED_TOOLS or is_error:
            return PostToolUseResult()

        warnings: list[dict[str, str]] = []

        # Check code argument for SQL or Python
        code = arguments.get("code", "") or arguments.get("sql", "")
        if not code:
            return PostToolUseResult()

        # Analyze SQL JOINs
        if re.search(r"\bJOIN\b", code, re.IGNORECASE):
            warnings.extend(_analyze_sql_joins(code))

        # Analyze pandas merges
        if _PANDAS_MERGE_PATTERN.search(code):
            warnings.extend(_analyze_pandas_merges(code))

        if not warnings:
            return PostToolUseResult()

        # Emit warning events
        for w in warnings:
            context.emit(
                "harness.warning",
                {
                    "type": "temporal_join",
                    "severity": "medium",
                    "message": w["message"],
                    "details": w,
                },
            )

        # Append warnings to result
        warning_text = "\n".join(
            f"- {w['message']}" for w in warnings
        )
        return PostToolUseResult(
            modified_result=(
                f"{result}\n\n"
                f"[TEMPORAL JOIN WARNING] Potential future information "
                f"leakage detected:\n{warning_text}"
            ),
        )
