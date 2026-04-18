"""BacktrackTriggerHook tests — TDD RED phase.

Tests backtracking: performance threshold detection, depth limits,
WorkflowTracker reverse transitions, and context preservation.
"""

import json

import pytest

from ds_agent.agent.ds_workflow_hooks import WorkflowTrackerHook
from ds_agent.agent.hooks import HookContext
from ds_agent.domain.value_objects.backtrack import BacktrackDecision, PreviousAttempt

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _ctx(**kwargs) -> HookContext:
    events: list[tuple[str, dict]] = []
    ctx = HookContext(emit=lambda e, p: events.append((e, p)), **kwargs)
    ctx._events = events  # type: ignore[attr-defined]
    return ctx


def _eval_result(metrics: dict[str, float]) -> str:
    """Simulate evaluate_model result with metrics."""
    return json.dumps({"output": json.dumps(metrics), "rc": 0})


def _poor_eval_result(accuracy: float = 0.55) -> str:
    """Simulate a poor evaluation result (below typical baselines)."""
    return json.dumps({
        "output": f"test_accuracy: {accuracy}\ntrain_accuracy: {accuracy + 0.05}",
        "rc": 0,
    })


# ---------------------------------------------------------------------------
# Domain Value Object tests
# ---------------------------------------------------------------------------


class TestBacktrackDecision:
    def test_basic_decision(self):
        d = BacktrackDecision(
            target_stage="feature_eng",
            reason="overfitting",
            previous_attempts=(
                PreviousAttempt(
                    stage="evaluation",
                    metrics={"accuracy": 0.72},
                    reason="train-test gap > 15%",
                ),
            ),
        )
        assert d.target_stage == "feature_eng"
        assert d.backtrack_count == 1
        assert d.should_stop is False

    def test_stop_decision(self):
        d = BacktrackDecision(
            target_stage="eda",
            reason="max backtrack depth reached",
            previous_attempts=(
                PreviousAttempt("evaluation", {"accuracy": 0.72}, "overfitting"),
                PreviousAttempt("evaluation", {"accuracy": 0.68}, "underfitting"),
            ),
            should_stop=True,
        )
        assert d.should_stop is True
        assert d.backtrack_count == 2

    def test_frozen_immutability(self):
        d = BacktrackDecision(
            target_stage="feature_eng",
            reason="overfitting",
            previous_attempts=(),
        )
        with pytest.raises(AttributeError):
            d.target_stage = "eda"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BacktrackTriggerHook tests
# ---------------------------------------------------------------------------


class TestBacktrackTriggerDetection:
    """Test 0-2.1: Performance below threshold triggers backtrack decision."""

    @pytest.mark.asyncio
    async def test_poor_performance_triggers_backtrack(self):
        from ds_agent.agent.backtrack_hook import BacktrackTriggerHook

        hook = BacktrackTriggerHook()
        ctx = _ctx()

        # Simulate evaluation with poor accuracy
        await hook.post_tool_use(
            "evaluate_model",
            {},
            _poor_eval_result(accuracy=0.52),
            False,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        backtrack_events = [e for e in events if e[0] == "backtrack.trigger"]
        assert len(backtrack_events) == 1
        payload = backtrack_events[0][1]
        assert payload["target_stage"] in ("feature_eng", "eda", "data_loading")
        assert "reason" in payload

    @pytest.mark.asyncio
    async def test_good_performance_no_backtrack(self):
        from ds_agent.agent.backtrack_hook import BacktrackTriggerHook

        hook = BacktrackTriggerHook()
        ctx = _ctx()

        # Good accuracy — no backtrack
        good_result = json.dumps({
            "output": "test_accuracy: 0.92\ntrain_accuracy: 0.94",
            "rc": 0,
        })
        await hook.post_tool_use("evaluate_model", {}, good_result, False, ctx)

        events = ctx._events  # type: ignore[attr-defined]
        backtrack_events = [e for e in events if e[0] == "backtrack.trigger"]
        assert len(backtrack_events) == 0

    @pytest.mark.asyncio
    async def test_ignores_non_evaluation_tools(self):
        from ds_agent.agent.backtrack_hook import BacktrackTriggerHook

        hook = BacktrackTriggerHook()
        ctx = _ctx()

        await hook.post_tool_use("execute_code", {}, "ok", False, ctx)

        events = ctx._events  # type: ignore[attr-defined]
        backtrack_events = [e for e in events if e[0] == "backtrack.trigger"]
        assert len(backtrack_events) == 0

    @pytest.mark.asyncio
    async def test_ignores_errors(self):
        from ds_agent.agent.backtrack_hook import BacktrackTriggerHook

        hook = BacktrackTriggerHook()
        ctx = _ctx()

        await hook.post_tool_use(
            "evaluate_model", {}, _poor_eval_result(0.50), True, ctx
        )

        events = ctx._events  # type: ignore[attr-defined]
        backtrack_events = [e for e in events if e[0] == "backtrack.trigger"]
        assert len(backtrack_events) == 0


class TestBacktrackDepthLimit:
    """Test 0-2.2: Backtracking depth limited to max 2."""

    @pytest.mark.asyncio
    async def test_stops_after_max_depth(self):
        from ds_agent.agent.backtrack_hook import BacktrackTriggerHook

        hook = BacktrackTriggerHook(max_backtracks=2)
        ctx = _ctx()

        # Trigger 2 backtracks
        for _ in range(2):
            await hook.post_tool_use(
                "evaluate_model", {}, _poor_eval_result(0.50), False, ctx
            )

        # 3rd attempt should NOT trigger another backtrack
        await hook.post_tool_use(
            "evaluate_model", {}, _poor_eval_result(0.50), False, ctx
        )

        events = ctx._events  # type: ignore[attr-defined]
        backtrack_events = [e for e in events if e[0] == "backtrack.trigger"]
        stop_events = [e for e in events if e[0] == "backtrack.stop"]
        assert len(backtrack_events) == 2
        assert len(stop_events) == 1


class TestWorkflowTrackerRewind:
    """Test 0-2.3: WorkflowTracker supports reverse state transitions."""

    def test_rewind_to_stage(self):
        from ds_agent.agent.backtrack_hook import rewind_tracker_to_stage

        tracker = WorkflowTrackerHook()
        # Simulate stages reaching evaluation
        tracker._stages["data_loading"] = "done"
        tracker._stages["profiling"] = "done"
        tracker._stages["eda"] = "done"
        tracker._stages["feature_eng"] = "done"
        tracker._stages["modeling"] = "done"
        tracker._stages["evaluation"] = "done"

        rewind_tracker_to_stage(tracker, "feature_eng")

        assert tracker._stages["data_loading"] == "done"
        assert tracker._stages["profiling"] == "done"
        assert tracker._stages["eda"] == "done"
        assert tracker._stages["feature_eng"] == "pending"
        assert tracker._stages["modeling"] == "pending"
        assert tracker._stages["evaluation"] == "pending"

    def test_rewind_preserves_earlier_stages(self):
        from ds_agent.agent.backtrack_hook import rewind_tracker_to_stage

        tracker = WorkflowTrackerHook()
        tracker._stages["data_loading"] = "done"
        tracker._stages["profiling"] = "done"

        rewind_tracker_to_stage(tracker, "profiling")

        assert tracker._stages["data_loading"] == "done"
        assert tracker._stages["profiling"] == "pending"

    def test_completeness_after_rewind(self):
        from ds_agent.agent.backtrack_hook import rewind_tracker_to_stage

        tracker = WorkflowTrackerHook()
        for stage in ("data_loading", "profiling", "eda", "feature_eng", "modeling", "evaluation"):
            tracker._stages[stage] = "done"

        rewind_tracker_to_stage(tracker, "feature_eng")
        comp = tracker.get_completeness()
        assert comp["completed"] == 3  # data_loading, profiling, eda


class TestBacktrackContextPreservation:
    """Test 0-2.4: Previous attempt context is preserved in backtrack event."""

    @pytest.mark.asyncio
    async def test_previous_attempt_in_event(self):
        from ds_agent.agent.backtrack_hook import BacktrackTriggerHook

        hook = BacktrackTriggerHook()
        ctx = _ctx()

        # First poor evaluation
        await hook.post_tool_use(
            "evaluate_model", {}, _poor_eval_result(0.52), False, ctx
        )

        events = ctx._events  # type: ignore[attr-defined]
        backtrack_events = [e for e in events if e[0] == "backtrack.trigger"]
        payload = backtrack_events[0][1]
        assert "previous_attempts" in payload

    @pytest.mark.asyncio
    async def test_second_backtrack_has_history(self):
        from ds_agent.agent.backtrack_hook import BacktrackTriggerHook

        hook = BacktrackTriggerHook(max_backtracks=3)
        ctx = _ctx()

        # First backtrack
        await hook.post_tool_use(
            "evaluate_model", {}, _poor_eval_result(0.52), False, ctx
        )
        # Second backtrack
        await hook.post_tool_use(
            "evaluate_model", {}, _poor_eval_result(0.48), False, ctx
        )

        events = ctx._events  # type: ignore[attr-defined]
        backtrack_events = [e for e in events if e[0] == "backtrack.trigger"]
        assert len(backtrack_events) == 2
        # Second event should reference the first attempt
        second_payload = backtrack_events[1][1]
        assert len(second_payload["previous_attempts"]) >= 1


class TestBacktrackModifiedResult:
    """Verify the hook appends backtrack instruction to the result."""

    @pytest.mark.asyncio
    async def test_modified_result_contains_instruction(self):
        from ds_agent.agent.backtrack_hook import BacktrackTriggerHook

        hook = BacktrackTriggerHook()
        ctx = _ctx()

        result = await hook.post_tool_use(
            "evaluate_model", {}, _poor_eval_result(0.52), False, ctx
        )

        assert result.modified_result is not None
        assert "backtrack" in result.modified_result.lower()


class TestBacktrackHookMetadata:
    """Verify hook priority and name."""

    def test_priority(self):
        from ds_agent.agent.backtrack_hook import BacktrackTriggerHook

        hook = BacktrackTriggerHook()
        assert hook.priority == 37

    def test_name(self):
        from ds_agent.agent.backtrack_hook import BacktrackTriggerHook

        hook = BacktrackTriggerHook()
        assert hook.name == "backtrack_trigger"
