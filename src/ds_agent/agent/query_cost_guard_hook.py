"""QueryCostGuardHook — SQL query cost estimation and guard.

Priority 15: runs after PermissionHook (10) and before BudgetGuard (20).

Before any sql_query tool call, estimates query cost and DENYs
if the estimated cost exceeds configured thresholds.
"""

from __future__ import annotations

from ds_agent.agent.hooks import (
    HookAction,
    HookContext,
    PreToolUseResult,
    ToolHook,
)
from ds_agent.application.services.warehouse_service import estimate_query_cost
from ds_agent.domain.value_objects.connector import QuerySpec, validate_sql_safety


class QueryCostGuardHook(ToolHook):
    """Guards against expensive or unsafe SQL queries.

    Checks:
    1. SQL safety (no DDL/DML/DCL)
    2. Estimated cost vs per-query threshold
    3. Session cumulative cost vs session threshold
    """

    name = "query_cost_guard"
    priority = 15

    def __init__(
        self,
        max_cost_per_query_usd: float = 10.0,
        max_cost_per_session_usd: float = 100.0,
    ) -> None:
        self._max_per_query = max_cost_per_query_usd
        self._max_per_session = max_cost_per_session_usd
        self._session_cost_usd = 0.0

    async def pre_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        context: HookContext,
    ) -> PreToolUseResult:
        if tool_name != "sql_query":
            return PreToolUseResult()

        sql = arguments.get("sql", "")
        if not sql:
            return PreToolUseResult(
                action=HookAction.DENY,
                deny_reason="Empty SQL query",
            )

        # 1. Safety check
        validation = validate_sql_safety(sql)
        if not validation.is_safe:
            reasons = "; ".join(validation.violations)
            return PreToolUseResult(
                action=HookAction.DENY,
                deny_reason=f"SQL safety violation: {reasons}",
            )

        # 2. Cost estimation (use hook-provided value first, then adapter)
        estimated_cost = 0.0
        modified_arguments = dict(arguments)
        estimated_cost_raw = arguments.get("estimated_cost_usd")
        if isinstance(estimated_cost_raw, (int, float)) and not isinstance(
            estimated_cost_raw, bool
        ):
            estimated_cost = float(estimated_cost_raw)
        else:
            timeout_override = arguments.get("timeout")
            if not isinstance(timeout_override, int) or isinstance(timeout_override, bool):
                timeout_override = None

            connector_name = arguments.get("connector_name", "default")
            if not isinstance(connector_name, str) or not connector_name:
                connector_name = "default"

            estimate = estimate_query_cost(
                QuerySpec(
                    sql=sql,
                    connector_name=connector_name,
                    timeout_override=timeout_override,
                )
            )
            if estimate is not None:
                estimated_cost = float(estimate.estimated_cost_usd)
                modified_arguments["estimated_cost_usd"] = estimated_cost

        if estimated_cost > self._max_per_query:
            return PreToolUseResult(
                action=HookAction.DENY,
                deny_reason=(
                    f"Estimated query cost ${estimated_cost:.2f} exceeds "
                    f"limit ${self._max_per_query:.2f}/query. "
                    f"Add LIMIT, WHERE filters, or use sampling."
                ),
            )

        # 3. Session cumulative cost check
        if self._session_cost_usd + estimated_cost > self._max_per_session:
            return PreToolUseResult(
                action=HookAction.DENY,
                deny_reason=(
                    f"Session SQL cost would reach "
                    f"${self._session_cost_usd + estimated_cost:.2f}, "
                    f"exceeding limit ${self._max_per_session:.2f}/session."
                ),
            )

        if modified_arguments != arguments:
            return PreToolUseResult(
                action=HookAction.MODIFY,
                modified_arguments=modified_arguments,
            )

        return PreToolUseResult()

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name == "sql_query" and not is_error:
            cost = arguments.get("estimated_cost_usd", 0.0)
            if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                self._session_cost_usd += cost
        return PostToolUseResult()


# Import here to avoid circular import issue with the type
from ds_agent.agent.hooks import PostToolUseResult  # noqa: E402
