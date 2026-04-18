"""Integration test: SelfDebugHook wired into HookRegistry.

Test 0-1.5: Verify SelfDebugHook works correctly within the full hook pipeline,
respecting priority ordering and not interfering with other hooks.
"""

import json

import pytest

from ds_agent.agent.hooks import HookContext, HookRegistry
from ds_agent.agent.self_debug_hook import SelfDebugHook


def _ctx(**kwargs) -> HookContext:
    events: list[tuple[str, dict]] = []
    ctx = HookContext(emit=lambda e, p: events.append((e, p)), **kwargs)
    ctx._events = events  # type: ignore[attr-defined]
    return ctx


def _error_result(msg: str) -> str:
    return json.dumps({"error": msg, "rc": 1})


class TestSelfDebugInRegistry:
    """SelfDebugHook integrates correctly with HookRegistry."""

    @pytest.mark.asyncio
    async def test_hook_runs_in_registry_post_hooks(self):
        """SelfDebugHook fires in run_post_hooks when is_error=True."""
        registry = HookRegistry()
        registry.register(SelfDebugHook())
        ctx = _ctx()

        await registry.run_post_hooks(
            "execute_code",
            {"code": "bad"},
            _error_result("NameError: name 'bad' is not defined"),
            True,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        debug_events = [e for e in events if e[0] == "debug.attempt"]
        assert len(debug_events) == 1

    @pytest.mark.asyncio
    async def test_hook_does_not_interfere_with_other_hooks(self):
        """Other hooks still fire normally alongside SelfDebugHook."""
        from ds_agent.agent.hooks import PostToolUseResult, ToolHook

        class DummyHook(ToolHook):
            name = "dummy"
            priority = 50
            fired = False

            async def post_tool_use(self, tool_name, arguments, result, is_error, context):
                self.fired = True
                return PostToolUseResult()

        dummy = DummyHook()
        registry = HookRegistry()
        registry.register(SelfDebugHook())
        registry.register(dummy)
        ctx = _ctx()

        await registry.run_post_hooks(
            "execute_code", {}, _error_result("Err"), True, ctx
        )

        assert dummy.fired is True

    @pytest.mark.asyncio
    async def test_priority_ordering_with_other_hooks(self):
        """SelfDebugHook (priority=33) runs between priority 30 and 35 hooks."""
        from ds_agent.agent.hooks import PostToolUseResult, ToolHook

        execution_order: list[str] = []

        class Hook30(ToolHook):
            name = "hook_30"
            priority = 30

            async def post_tool_use(self, tool_name, arguments, result, is_error, context):
                execution_order.append("hook_30")
                return PostToolUseResult()

        class Hook35(ToolHook):
            name = "hook_35"
            priority = 35

            async def post_tool_use(self, tool_name, arguments, result, is_error, context):
                execution_order.append("hook_35")
                return PostToolUseResult()

        class TrackingSelfDebugHook(SelfDebugHook):
            async def post_tool_use(self, tool_name, arguments, result, is_error, context):
                execution_order.append("self_debug")
                return await super().post_tool_use(
                    tool_name, arguments, result, is_error, context
                )

        registry = HookRegistry()
        registry.register(Hook35())
        registry.register(TrackingSelfDebugHook())
        registry.register(Hook30())
        ctx = _ctx()

        await registry.run_post_hooks("execute_code", {}, _error_result("Err"), True, ctx)

        assert execution_order == ["hook_30", "self_debug", "hook_35"]

    @pytest.mark.asyncio
    async def test_escalation_after_repeated_failures(self):
        """Full escalation flow through registry — 3 failures then escalation."""
        registry = HookRegistry()
        hook = SelfDebugHook(max_retries=3)
        registry.register(hook)
        ctx = _ctx()

        for _ in range(3):
            await registry.run_post_hooks(
                "execute_code", {}, _error_result("Err"), True, ctx
            )

        # 4th call triggers escalation
        post_result = await registry.run_post_hooks(
            "execute_code", {}, _error_result("Err"), True, ctx
        )

        events = ctx._events  # type: ignore[attr-defined]
        escalation_events = [e for e in events if e[0] == "debug.escalation"]
        assert len(escalation_events) == 1

    @pytest.mark.asyncio
    async def test_no_event_on_non_error(self):
        """SelfDebugHook stays quiet when tool succeeds."""
        registry = HookRegistry()
        registry.register(SelfDebugHook())
        ctx = _ctx()

        await registry.run_post_hooks(
            "execute_code",
            {},
            json.dumps({"output": "42", "rc": 0}),
            False,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        debug_events = [e for e in events if e[0] in ("debug.attempt", "debug.escalation")]
        assert len(debug_events) == 0
