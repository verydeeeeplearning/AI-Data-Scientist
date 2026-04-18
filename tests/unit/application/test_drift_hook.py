"""Drift hook tests for PLAN 17 Phase 5."""

from __future__ import annotations

import pytest

from ds_agent.agent.ds_workflow_hooks import DriftDetectionHook
from ds_agent.agent.hooks import HookContext


def _ctx() -> HookContext:
    events: list[tuple[str, dict]] = []
    ctx = HookContext(
        emit=lambda event, payload: events.append((event, payload)),
        user_message="Evaluate the deployed model against the new batch.",
    )
    ctx._events = events  # type: ignore[attr-defined]
    return ctx


class TestDriftDetectionHook:
    @pytest.mark.asyncio
    async def test_emits_event_when_drift_detected(self):
        hook = DriftDetectionHook()
        ctx = _ctx()

        result = await hook.post_tool_use(
            "evaluate_model",
            {
                "reference_data": [{"feature": 0}] * 20,
                "current_data": [{"feature": 100}] * 20,
            },
            "evaluation complete",
            False,
            ctx,
        )

        assert "Drift monitoring" in (result.modified_result or "")
        events = ctx._events  # type: ignore[attr-defined]
        assert len(events) == 1
        assert events[0][0] == "drift.detected"
        assert events[0][1]["overall_status"] == "danger"

    @pytest.mark.asyncio
    async def test_ignores_non_evaluation_tools(self):
        hook = DriftDetectionHook()
        ctx = _ctx()

        result = await hook.post_tool_use(
            "run_eda",
            {
                "reference_data": [{"feature": 0}] * 10,
                "current_data": [{"feature": 10}] * 10,
            },
            "ok",
            False,
            ctx,
        )

        assert result.modified_result is None
        assert ctx._events == []  # type: ignore[attr-defined]
