"""Integration test: BacktrackTriggerHook within HookRegistry.

Test 0-2.5: Full pipeline simulation — evaluation failure triggers
automatic backtracking within the hook registry.
"""

import json

import pytest

from ds_agent.agent.backtrack_hook import BacktrackTriggerHook
from ds_agent.agent.hooks import HookContext, HookRegistry


def _ctx(**kwargs) -> HookContext:
    events: list[tuple[str, dict]] = []
    ctx = HookContext(emit=lambda e, p: events.append((e, p)), **kwargs)
    ctx._events = events  # type: ignore[attr-defined]
    return ctx


def _poor_eval_result(accuracy: float = 0.50) -> str:
    return json.dumps({
        "output": f"test_accuracy: {accuracy}\ntrain_accuracy: {accuracy + 0.05}",
        "rc": 0,
    })


class TestBacktrackInRegistry:
    @pytest.mark.asyncio
    async def test_backtrack_fires_in_registry(self):
        registry = HookRegistry()
        registry.register(BacktrackTriggerHook())
        ctx = _ctx()

        await registry.run_post_hooks(
            "evaluate_model", {}, _poor_eval_result(0.50), False, ctx
        )

        events = ctx._events  # type: ignore[attr-defined]
        backtrack_events = [e for e in events if e[0] == "backtrack.trigger"]
        assert len(backtrack_events) == 1

    @pytest.mark.asyncio
    async def test_no_backtrack_on_good_performance(self):
        registry = HookRegistry()
        registry.register(BacktrackTriggerHook())
        ctx = _ctx()

        good_result = json.dumps({
            "output": "test_accuracy: 0.92\ntrain_accuracy: 0.93",
            "rc": 0,
        })
        await registry.run_post_hooks("evaluate_model", {}, good_result, False, ctx)

        events = ctx._events  # type: ignore[attr-defined]
        backtrack_events = [e for e in events if e[0] == "backtrack.trigger"]
        assert len(backtrack_events) == 0

    @pytest.mark.asyncio
    async def test_coexists_with_other_hooks(self):
        from ds_agent.agent.hooks import PostToolUseResult, ToolHook

        class DummyHook(ToolHook):
            name = "dummy_post"
            priority = 50
            fired = False

            async def post_tool_use(self, tool_name, arguments, result, is_error, context):
                self.fired = True
                return PostToolUseResult()

        dummy = DummyHook()
        registry = HookRegistry()
        registry.register(BacktrackTriggerHook())
        registry.register(dummy)
        ctx = _ctx()

        await registry.run_post_hooks(
            "evaluate_model", {}, _poor_eval_result(0.50), False, ctx
        )

        assert dummy.fired is True

    @pytest.mark.asyncio
    async def test_priority_between_35_and_40(self):
        """BacktrackTriggerHook (37) runs between OverfittingDetector (35) and ModelSanityCheck (40)."""
        from ds_agent.agent.hooks import PostToolUseResult, ToolHook

        order: list[str] = []

        class Hook35(ToolHook):
            name = "h35"
            priority = 35

            async def post_tool_use(self, tool_name, arguments, result, is_error, context):
                order.append("h35")
                return PostToolUseResult()

        class Hook40(ToolHook):
            name = "h40"
            priority = 40

            async def post_tool_use(self, tool_name, arguments, result, is_error, context):
                order.append("h40")
                return PostToolUseResult()

        class TrackingBacktrackHook(BacktrackTriggerHook):
            async def post_tool_use(self, tool_name, arguments, result, is_error, context):
                order.append("backtrack")
                return await super().post_tool_use(
                    tool_name, arguments, result, is_error, context
                )

        registry = HookRegistry()
        registry.register(Hook40())
        registry.register(TrackingBacktrackHook())
        registry.register(Hook35())
        ctx = _ctx()

        await registry.run_post_hooks(
            "evaluate_model", {}, _poor_eval_result(0.50), False, ctx
        )

        assert order == ["h35", "backtrack", "h40"]
