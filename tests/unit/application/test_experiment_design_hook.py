"""Experiment design hook tests for PLAN 17 Phase 5."""

from __future__ import annotations

import json

import pytest

from ds_agent.agent.ds_workflow_hooks import ExperimentDesignHook
from ds_agent.agent.hooks import HookContext


def _ctx() -> HookContext:
    events: list[tuple[str, dict]] = []
    ctx = HookContext(
        emit=lambda event, payload: events.append((event, payload)),
        user_message="Analyze this A/B test result.",
    )
    ctx._events = events  # type: ignore[attr-defined]
    return ctx


class TestExperimentDesignHook:
    @pytest.mark.asyncio
    async def test_warns_on_srm_failure(self):
        hook = ExperimentDesignHook()
        ctx = _ctx()

        result = await hook.post_tool_use(
            "ab_test",
            {
                "action": "analyze",
                "control_n": 4800,
                "treatment_n": 5200,
                "expected_control_ratio": 0.5,
                "expected_treatment_ratio": 0.5,
            },
            json.dumps({"p_value": 0.03, "winner": "treatment"}),
            False,
            ctx,
        )

        assert "SRM" in (result.modified_result or "")
        events = ctx._events  # type: ignore[attr-defined]
        assert events[0][0] == "experiment.design_warning"
        assert events[0][1]["checks"]["srm"]["is_valid"] is False

    @pytest.mark.asyncio
    async def test_warns_when_underpowered(self):
        hook = ExperimentDesignHook()
        ctx = _ctx()

        result = await hook.post_tool_use(
            "ab_test",
            {
                "action": "design",
                "effect_size": 0.05,
                "observed_total_n": 400,
            },
            json.dumps({"status": "designed"}),
            False,
            ctx,
        )

        assert "underpowered" in (result.modified_result or "").lower()
