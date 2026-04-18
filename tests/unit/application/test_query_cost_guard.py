"""QueryCostGuardHook tests."""

import pytest

from ds_agent.agent.hooks import HookAction, HookContext


def _ctx(**kwargs) -> HookContext:
    return HookContext(**kwargs)


class TestQueryCostGuardSafety:
    """SQL safety validation through the hook."""

    @pytest.mark.asyncio
    async def test_allows_safe_select(self):
        from ds_agent.agent.query_cost_guard_hook import QueryCostGuardHook

        hook = QueryCostGuardHook()
        result = await hook.pre_tool_use(
            "sql_query",
            {"sql": "SELECT count(*) FROM users"},
            _ctx(),
        )
        assert result.action == HookAction.ALLOW

    @pytest.mark.asyncio
    async def test_denies_drop_table(self):
        from ds_agent.agent.query_cost_guard_hook import QueryCostGuardHook

        hook = QueryCostGuardHook()
        result = await hook.pre_tool_use(
            "sql_query",
            {"sql": "DROP TABLE users"},
            _ctx(),
        )
        assert result.action == HookAction.DENY
        assert "safety" in result.deny_reason.lower()

    @pytest.mark.asyncio
    async def test_denies_empty_sql(self):
        from ds_agent.agent.query_cost_guard_hook import QueryCostGuardHook

        hook = QueryCostGuardHook()
        result = await hook.pre_tool_use("sql_query", {"sql": ""}, _ctx())
        assert result.action == HookAction.DENY

    @pytest.mark.asyncio
    async def test_ignores_non_sql_tools(self):
        from ds_agent.agent.query_cost_guard_hook import QueryCostGuardHook

        hook = QueryCostGuardHook()
        result = await hook.pre_tool_use(
            "execute_code", {"code": "print(1)"}, _ctx()
        )
        assert result.action == HookAction.ALLOW


class TestQueryCostGuardCost:
    """Cost threshold enforcement."""

    @pytest.mark.asyncio
    async def test_denies_expensive_query(self):
        from ds_agent.agent.query_cost_guard_hook import QueryCostGuardHook

        hook = QueryCostGuardHook(max_cost_per_query_usd=10.0)
        result = await hook.pre_tool_use(
            "sql_query",
            {"sql": "SELECT * FROM huge_table", "estimated_cost_usd": 50.0},
            _ctx(),
        )
        assert result.action == HookAction.DENY
        assert "50.00" in result.deny_reason
        assert "10.00" in result.deny_reason

    @pytest.mark.asyncio
    async def test_allows_cheap_query(self):
        from ds_agent.agent.query_cost_guard_hook import QueryCostGuardHook

        hook = QueryCostGuardHook(max_cost_per_query_usd=10.0)
        result = await hook.pre_tool_use(
            "sql_query",
            {"sql": "SELECT 1", "estimated_cost_usd": 2.0},
            _ctx(),
        )
        assert result.action == HookAction.ALLOW

    @pytest.mark.asyncio
    async def test_session_cumulative_cost(self):
        from ds_agent.agent.query_cost_guard_hook import QueryCostGuardHook

        hook = QueryCostGuardHook(
            max_cost_per_query_usd=50.0,
            max_cost_per_session_usd=20.0,
        )

        # First query: $8
        r1 = await hook.pre_tool_use(
            "sql_query",
            {"sql": "SELECT 1", "estimated_cost_usd": 8.0},
            _ctx(),
        )
        assert r1.action == HookAction.ALLOW
        await hook.post_tool_use("sql_query", {"estimated_cost_usd": 8.0}, "ok", False, _ctx())

        # Second query: $8 (total $16, still ok)
        r2 = await hook.pre_tool_use(
            "sql_query",
            {"sql": "SELECT 2", "estimated_cost_usd": 8.0},
            _ctx(),
        )
        assert r2.action == HookAction.ALLOW
        await hook.post_tool_use("sql_query", {"estimated_cost_usd": 8.0}, "ok", False, _ctx())

        # Third query: $8 (total would be $24 > $20)
        r3 = await hook.pre_tool_use(
            "sql_query",
            {"sql": "SELECT 3", "estimated_cost_usd": 8.0},
            _ctx(),
        )
        assert r3.action == HookAction.DENY
        assert "session" in r3.deny_reason.lower()


class TestQueryCostGuardMeta:
    def test_priority(self):
        from ds_agent.agent.query_cost_guard_hook import QueryCostGuardHook

        assert QueryCostGuardHook().priority == 15

    def test_name(self):
        from ds_agent.agent.query_cost_guard_hook import QueryCostGuardHook

        assert QueryCostGuardHook().name == "query_cost_guard"
