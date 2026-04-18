"""Governed SQL query tool backed by registered warehouse adapters."""

from __future__ import annotations

import json

from ds_agent.application.services.warehouse_service import (
    estimate_query_cost,
    execute_query,
    get_warehouse_adapter,
)
from ds_agent.domain.value_objects.connector import QuerySpec, validate_sql_safety
from ds_agent.tools.path_utils import get_active_workspace
from ds_agent.tools.registry import tool
from ds_agent.tools.sql_result_summarizer import summarize_sql_rows


@tool(
    name="sql_query",
    description=(
        "Execute a governed read-only SQL query through a configured warehouse "
        "adapter. Returns row preview, row count, summary statistics, and cost metadata."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "Read-only SQL query to execute.",
            },
            "connector_name": {
                "type": "string",
                "default": "default",
                "description": "Configured warehouse connector name.",
            },
            "timeout": {
                "type": "integer",
                "default": 30,
                "description": "Per-query timeout in seconds.",
            },
            "estimated_cost_usd": {
                "type": "number",
                "description": "Internal hook-populated cost estimate for the query.",
            },
        },
        "required": ["sql"],
    },
    timeout=60,
    prompt=(
        "Runs a governed SQL query through a configured read-only warehouse adapter.\n"
        "- Only use SELECT/WITH/EXPLAIN/SHOW/DESCRIBE statements\n"
        "- Add LIMIT for exploratory questions when the result may be large\n"
        "- Use connector_name when multiple warehouses are configured"
    ),
)
def sql_query(
    sql: str,
    connector_name: str = "default",
    timeout: int = 30,
    estimated_cost_usd: float | None = None,
) -> str:
    if timeout <= 0:
        return json.dumps({"error": "timeout must be a positive integer", "tool": "sql_query"})

    validation = validate_sql_safety(sql)
    if not validation.is_safe:
        reasons = "; ".join(validation.violations)
        return json.dumps(
            {"error": f"SQL safety violation: {reasons}", "tool": "sql_query"}
        )

    adapter = get_warehouse_adapter(connector_name)
    if adapter is None:
        return json.dumps(
            {
                "error": (
                    f"No warehouse adapter configured for connector '{connector_name}'."
                ),
                "tool": "sql_query",
            }
        )

    adapter_validation = adapter.validate_query(sql)
    if not adapter_validation.is_safe:
        reasons = "; ".join(adapter_validation.violations)
        return json.dumps(
            {"error": f"Adapter rejected SQL query: {reasons}", "tool": "sql_query"}
        )

    spec = QuerySpec(
        sql=sql,
        connector_name=connector_name,
        timeout_override=timeout,
    )

    try:
        cost = estimated_cost_usd
        if cost is None:
            estimate = estimate_query_cost(spec)
            cost = estimate.estimated_cost_usd if estimate is not None else 0.0

        rows = execute_query(spec)
        summary = summarize_sql_rows(rows, workspace_dir=get_active_workspace())
    except Exception as exc:
        return json.dumps({"error": str(exc), "tool": "sql_query"})

    payload: dict[str, object] = {
        "connector_name": connector_name,
        "columns": summary.columns,
        "data": summary.data,
        "row_count": summary.row_count,
        "summary_stats": summary.summary_stats,
        "cost_usd": cost,
        "truncated": summary.truncated,
    }
    if summary.saved_result_path is not None:
        payload["saved_result_path"] = summary.saved_result_path

    return json.dumps(payload, default=str)
