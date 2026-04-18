"""Table trust lookup tool backed by semantic memory."""

from __future__ import annotations

from ds_agent.tools._semantic_common import (
    get_semantic_memory_container,
    semantic_error,
    semantic_result,
)
from ds_agent.tools.registry import tool


@tool(
    name="describe_table_trust",
    description=(
        "Inspect semantic trust metadata for one or more tables. Returns trust grade, "
        "owner, freshness contract, and execution policy warnings."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "fqtns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Fully qualified table names to evaluate.",
            },
            "allow_untrusted": {
                "type": "boolean",
                "default": False,
                "description": "When true, downgrade missing/untrusted tables to warnings.",
            },
        },
        "required": ["fqtns"],
    },
    prompt=(
        "Checks table trust before using warehouse data.\n"
        "- Use on referenced tables to see whether execution is safe, caveated, or blocked\n"
        "- Bronze or untrusted tables may require user/operator confirmation"
    ),
)
def describe_table_trust(fqtns: list[str], allow_untrusted: bool = False) -> str:
    if not fqtns:
        return semantic_error("fqtns must contain at least one table", tool_name="describe_table_trust")

    try:
        result = get_semantic_memory_container().check_table_trust.execute(
            fqtns,
            allow_untrusted=allow_untrusted,
        )
    except Exception as exc:
        return semantic_error(str(exc), tool_name="describe_table_trust")

    return semantic_result(
        {
            "action": result.action,
            "missing_tables": result.missing_tables,
            "warnings": result.warnings,
            "tables": [table.model_dump(mode="json") for table in result.tables],
        }
    )
