"""SelfDebugHook tests — TDD RED phase.

Tests the self-debugging loop: error detection, signature hashing,
retry counter management, escalation, and successful-fix reset.
"""

import json

import pytest

from ds_agent.agent.hooks import HookContext, PostToolUseResult
from ds_agent.domain.value_objects.self_debug import (
    DebugAction,
    ErrorCategory,
    SelfDebugDecision,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _ctx(**kwargs) -> HookContext:
    events: list[tuple[str, dict]] = []
    ctx = HookContext(emit=lambda e, p: events.append((e, p)), **kwargs)
    ctx._events = events  # type: ignore[attr-defined]
    return ctx


def _error_result(error_msg: str) -> str:
    """Simulate a tool error result in JSON format."""
    return json.dumps({"error": error_msg, "rc": 1})


def _success_result(output: str = "ok") -> str:
    return json.dumps({"output": output, "rc": 0})


# ---------------------------------------------------------------------------
# Domain Value Object tests
# ---------------------------------------------------------------------------


class TestSelfDebugDecision:
    def test_retry_decision(self):
        d = SelfDebugDecision(
            action=DebugAction.RETRY,
            error_category=ErrorCategory.CODE_BUG,
            suggestion="Fix the TypeError by casting to int",
            attempt_count=1,
            error_signature="TypeError:abc123",
        )
        assert d.should_retry is True
        assert d.should_escalate is False
        assert d.is_repeated_error is False

    def test_escalate_decision(self):
        d = SelfDebugDecision(
            action=DebugAction.ESCALATE,
            error_category=ErrorCategory.ENV_ERROR,
            suggestion="OOM — cannot resolve automatically",
            attempt_count=4,
            error_signature="MemoryError:def456",
        )
        assert d.should_retry is False
        assert d.should_escalate is True

    def test_repeated_error_detection(self):
        d = SelfDebugDecision(
            action=DebugAction.RETRY,
            error_category=ErrorCategory.CODE_BUG,
            suggestion="...",
            attempt_count=2,
            error_signature="TypeError:abc123",
            previous_signatures=("ValueError:xyz", "TypeError:abc123"),
        )
        assert d.is_repeated_error is True

    def test_frozen_immutability(self):
        d = SelfDebugDecision(
            action=DebugAction.RETRY,
            error_category=ErrorCategory.DATA_ERROR,
            suggestion="...",
            attempt_count=1,
            error_signature="FileNotFoundError:ghi789",
        )
        with pytest.raises(AttributeError):
            d.action = DebugAction.ESCALATE  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SelfDebugHook tests
# ---------------------------------------------------------------------------


class TestSelfDebugHookErrorDetection:
    """Test 0-1.1: SelfDebugHook detects errors and emits debug.attempt event."""

    @pytest.mark.asyncio
    async def test_emits_debug_attempt_on_tool_error(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook()
        ctx = _ctx()

        result = await hook.post_tool_use(
            "execute_code",
            {"code": "1/0"},
            _error_result("ZeroDivisionError: division by zero"),
            True,  # is_error
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        debug_events = [e for e in events if e[0] == "debug.attempt"]
        assert len(debug_events) == 1
        payload = debug_events[0][1]
        assert payload["tool_name"] == "execute_code"
        assert "error_category" in payload
        assert "suggestion" in payload
        assert payload["attempt"] >= 1

    @pytest.mark.asyncio
    async def test_classifies_data_error(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook()
        ctx = _ctx()

        await hook.post_tool_use(
            "data_loader",
            {"path": "missing.csv"},
            _error_result("FileNotFoundError: [Errno 2] No such file or directory: 'missing.csv'"),
            True,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        debug_events = [e for e in events if e[0] == "debug.attempt"]
        assert debug_events[0][1]["error_category"] == ErrorCategory.DATA_ERROR

    @pytest.mark.asyncio
    async def test_classifies_code_bug(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook()
        ctx = _ctx()

        await hook.post_tool_use(
            "execute_code",
            {"code": "x = 'a' + 1"},
            _error_result("TypeError: can only concatenate str (not \"int\") to str"),
            True,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        debug_events = [e for e in events if e[0] == "debug.attempt"]
        assert debug_events[0][1]["error_category"] == ErrorCategory.CODE_BUG

    @pytest.mark.asyncio
    async def test_classifies_env_error(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook()
        ctx = _ctx()

        await hook.post_tool_use(
            "execute_code",
            {"code": "import torch"},
            _error_result("ModuleNotFoundError: No module named 'torch'"),
            True,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        debug_events = [e for e in events if e[0] == "debug.attempt"]
        assert debug_events[0][1]["error_category"] == ErrorCategory.ENV_ERROR

    @pytest.mark.asyncio
    async def test_no_event_on_success(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook()
        ctx = _ctx()

        await hook.post_tool_use(
            "execute_code",
            {"code": "print(1)"},
            _success_result("1"),
            False,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        debug_events = [e for e in events if e[0] == "debug.attempt"]
        assert len(debug_events) == 0


class TestSelfDebugHookSignatureHashing:
    """Test 0-1.2: Error signature hashing detects repeated errors."""

    @pytest.mark.asyncio
    async def test_same_error_twice_sets_repeated_flag(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook()
        ctx = _ctx()

        # First TypeError
        await hook.post_tool_use(
            "execute_code",
            {"code": "x"},
            _error_result("TypeError: unsupported operand"),
            True,
            ctx,
        )

        # Same TypeError again
        await hook.post_tool_use(
            "execute_code",
            {"code": "x"},
            _error_result("TypeError: unsupported operand"),
            True,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        debug_events = [e for e in events if e[0] == "debug.attempt"]
        assert len(debug_events) == 2
        # Second attempt should note it's a repeated error
        assert debug_events[1][1].get("is_repeated") is True

    @pytest.mark.asyncio
    async def test_different_errors_not_repeated(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook()
        ctx = _ctx()

        await hook.post_tool_use(
            "execute_code", {}, _error_result("TypeError: bad type"), True, ctx
        )
        await hook.post_tool_use(
            "execute_code", {}, _error_result("ValueError: bad value"), True, ctx
        )

        events = ctx._events  # type: ignore[attr-defined]
        debug_events = [e for e in events if e[0] == "debug.attempt"]
        assert debug_events[1][1].get("is_repeated") is False


class TestSelfDebugHookRetryEscalation:
    """Test 0-1.3: Max retry count (3) triggers escalation."""

    @pytest.mark.asyncio
    async def test_escalation_after_max_retries(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook(max_retries=3)
        ctx = _ctx()

        # 3 failures
        for i in range(3):
            await hook.post_tool_use(
                "execute_code",
                {"code": f"attempt_{i}"},
                _error_result(f"Error attempt {i}"),
                True,
                ctx,
            )

        # 4th failure should escalate
        await hook.post_tool_use(
            "execute_code",
            {"code": "attempt_3"},
            _error_result("Error attempt 3"),
            True,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        escalation_events = [e for e in events if e[0] == "debug.escalation"]
        assert len(escalation_events) == 1
        payload = escalation_events[0][1]
        assert payload["tool_name"] == "execute_code"
        assert "error_history" in payload
        assert payload["reason"] == "max_retries_exceeded"

    @pytest.mark.asyncio
    async def test_modified_result_includes_escalation_message(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook(max_retries=3)
        ctx = _ctx()

        # Exhaust retries
        for i in range(3):
            await hook.post_tool_use(
                "execute_code", {}, _error_result(f"Err {i}"), True, ctx
            )

        # 4th call — should modify result to include escalation instruction
        result = await hook.post_tool_use(
            "execute_code", {}, _error_result("Err 3"), True, ctx
        )

        assert result.modified_result is not None
        assert "ask_user" in result.modified_result.lower() or "escalat" in result.modified_result.lower()


class TestSelfDebugHookCounterReset:
    """Test 0-1.4: Successful fix resets retry counter."""

    @pytest.mark.asyncio
    async def test_success_resets_counter(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook(max_retries=3)
        ctx = _ctx()

        # 2 failures
        await hook.post_tool_use("execute_code", {}, _error_result("Err 1"), True, ctx)
        await hook.post_tool_use("execute_code", {}, _error_result("Err 2"), True, ctx)

        # Success — should reset counter
        await hook.post_tool_use("execute_code", {}, _success_result(), False, ctx)

        # New error — counter should be 1, not 3
        await hook.post_tool_use("execute_code", {}, _error_result("New err"), True, ctx)

        events = ctx._events  # type: ignore[attr-defined]
        debug_events = [e for e in events if e[0] == "debug.attempt"]
        # Should have 3 debug attempts total (2 before success + 1 after)
        assert len(debug_events) == 3
        # The last attempt should be attempt #1 (reset after success)
        assert debug_events[2][1]["attempt"] == 1

    @pytest.mark.asyncio
    async def test_counter_tracks_per_tool(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook(max_retries=3)
        ctx = _ctx()

        # 2 failures on execute_code
        await hook.post_tool_use("execute_code", {}, _error_result("Err"), True, ctx)
        await hook.post_tool_use("execute_code", {}, _error_result("Err"), True, ctx)

        # 1 failure on data_loader — separate counter
        await hook.post_tool_use("data_loader", {}, _error_result("Err"), True, ctx)

        events = ctx._events  # type: ignore[attr-defined]
        debug_events = [e for e in events if e[0] == "debug.attempt"]
        # data_loader should be attempt 1
        data_loader_events = [e for e in debug_events if e[1]["tool_name"] == "data_loader"]
        assert data_loader_events[0][1]["attempt"] == 1


class TestSelfDebugHookPriority:
    """Verify hook priority is 33 (between LeakageDetection=30 and OverfittingDetector=35)."""

    def test_priority(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook()
        assert hook.priority == 33

    def test_name(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook()
        assert hook.name == "self_debug"


class TestSelfDebugHookSuggestion:
    """Verify the hook generates actionable suggestions for known error patterns."""

    @pytest.mark.asyncio
    async def test_suggestion_for_known_error(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook()
        ctx = _ctx()

        await hook.post_tool_use(
            "execute_code",
            {"code": "model.fit(X)"},
            _error_result("Input contains NaN, infinity or a value too large for dtype"),
            True,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        debug_events = [e for e in events if e[0] == "debug.attempt"]
        suggestion = debug_events[0][1]["suggestion"]
        assert len(suggestion) > 0  # Non-empty suggestion

    @pytest.mark.asyncio
    async def test_suggestion_for_unknown_error(self):
        from ds_agent.agent.self_debug_hook import SelfDebugHook

        hook = SelfDebugHook()
        ctx = _ctx()

        await hook.post_tool_use(
            "execute_code",
            {},
            _error_result("SomeCustomError: something weird happened"),
            True,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        debug_events = [e for e in events if e[0] == "debug.attempt"]
        # Should still produce a suggestion even for unknown errors
        assert debug_events[0][1]["error_category"] == ErrorCategory.UNKNOWN
        assert len(debug_events[0][1]["suggestion"]) > 0
