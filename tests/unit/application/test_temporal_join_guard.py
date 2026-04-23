"""TemporalJoinGuardHook tests."""

import pytest

from ds_agent.agent.hooks import HookContext


def _ctx(**kwargs) -> HookContext:
    events: list[tuple[str, dict]] = []
    ctx = HookContext(emit=lambda e, p: events.append((e, p)), **kwargs)
    ctx._events = events  # type: ignore[attr-defined]
    return ctx


class TestTemporalJoinGuardSQL:
    """Test 1-5.1 & 1-5.2: SQL JOIN temporal condition detection."""

    @pytest.mark.asyncio
    async def test_warns_on_join_without_temporal(self):
        from ds_agent.agent.temporal_join_guard_hook import TemporalJoinGuardHook

        hook = TemporalJoinGuardHook()
        ctx = _ctx()

        code = """
        SELECT u.*, e.event_type
        FROM users u
        JOIN events e ON u.id = e.user_id
        """
        await hook.post_tool_use(
            "execute_code", {"code": code}, "ok", False, ctx
        )

        events = ctx._events  # type: ignore[attr-defined]
        warnings = [e for e in events if e[0] == "harness.warning"]
        assert len(warnings) >= 1
        assert warnings[0][1]["type"] == "temporal_join"

    @pytest.mark.asyncio
    async def test_no_warning_with_temporal_condition(self):
        from ds_agent.agent.temporal_join_guard_hook import TemporalJoinGuardHook

        hook = TemporalJoinGuardHook()
        ctx = _ctx()

        code = """
        SELECT u.*, e.event_type
        FROM users u
        JOIN events e ON u.id = e.user_id
            AND e.created_at < u.label_date
        """
        await hook.post_tool_use(
            "execute_code", {"code": code}, "ok", False, ctx
        )

        events = ctx._events  # type: ignore[attr-defined]
        warnings = [e for e in events if e[0] == "harness.warning"]
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_no_warning_for_non_join_sql(self):
        from ds_agent.agent.temporal_join_guard_hook import TemporalJoinGuardHook

        hook = TemporalJoinGuardHook()
        ctx = _ctx()

        code = "SELECT count(*) FROM users WHERE active = 1"
        await hook.post_tool_use("execute_code", {"code": code}, "ok", False, ctx)

        events = ctx._events  # type: ignore[attr-defined]
        warnings = [e for e in events if e[0] == "harness.warning"]
        assert len(warnings) == 0


class TestTemporalJoinGuardPandas:
    """Test 1-5.3: Python pandas merge pattern detection."""

    @pytest.mark.asyncio
    async def test_warns_on_merge_without_temporal(self):
        from ds_agent.agent.temporal_join_guard_hook import TemporalJoinGuardHook

        hook = TemporalJoinGuardHook()
        ctx = _ctx()

        code = "result = pd.merge(users_df, orders_df, on='user_id')"
        await hook.post_tool_use(
            "execute_code", {"code": code}, "ok", False, ctx
        )

        events = ctx._events  # type: ignore[attr-defined]
        warnings = [e for e in events if e[0] == "harness.warning"]
        assert len(warnings) >= 1

    @pytest.mark.asyncio
    async def test_no_warning_with_temporal_column(self):
        from ds_agent.agent.temporal_join_guard_hook import TemporalJoinGuardHook

        hook = TemporalJoinGuardHook()
        ctx = _ctx()

        code = """
        orders_filtered = orders_df[orders_df['created_at'] < label_date]
        result = pd.merge(users_df, orders_filtered, on='user_id')
        """
        await hook.post_tool_use(
            "execute_code", {"code": code}, "ok", False, ctx
        )

        events = ctx._events  # type: ignore[attr-defined]
        warnings = [e for e in events if e[0] == "harness.warning"]
        assert len(warnings) == 0


class TestTemporalJoinGuardMeta:
    def test_priority(self):
        from ds_agent.agent.temporal_join_guard_hook import TemporalJoinGuardHook

        assert TemporalJoinGuardHook().priority == 28

    def test_name(self):
        from ds_agent.agent.temporal_join_guard_hook import TemporalJoinGuardHook

        assert TemporalJoinGuardHook().name == "temporal_join_guard"

    @pytest.mark.asyncio
    async def test_ignores_non_monitored_tools(self):
        from ds_agent.agent.temporal_join_guard_hook import TemporalJoinGuardHook

        hook = TemporalJoinGuardHook()
        ctx = _ctx()

        await hook.post_tool_use("data_loader", {"code": "JOIN"}, "ok", False, ctx)
        events = ctx._events  # type: ignore[attr-defined]
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_ignores_errors(self):
        from ds_agent.agent.temporal_join_guard_hook import TemporalJoinGuardHook

        hook = TemporalJoinGuardHook()
        ctx = _ctx()

        code = "SELECT * FROM a JOIN b ON a.id = b.id"
        await hook.post_tool_use("execute_code", {"code": code}, "err", True, ctx)
        events = ctx._events  # type: ignore[attr-defined]
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_modified_result_on_warning(self):
        from ds_agent.agent.temporal_join_guard_hook import TemporalJoinGuardHook

        hook = TemporalJoinGuardHook()
        ctx = _ctx()

        code = "SELECT * FROM a JOIN b ON a.id = b.id"
        result = await hook.post_tool_use(
            "execute_code", {"code": code}, "ok", False, ctx
        )

        assert result.modified_result is not None
        assert "TEMPORAL JOIN WARNING" in result.modified_result
