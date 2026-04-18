"""Tool tests for PLAN 17 Phase 5 and 6."""

from __future__ import annotations

import json

import pytest

from ds_agent.tools.ab_test_tools import ab_test
from ds_agent.tools.drift_tools import drift_monitor


class TestPlan17Tools:
    @pytest.mark.asyncio
    async def test_drift_monitor_returns_structured_report(self):
        result = await drift_monitor(
            reference_data=[{"feature": 0}] * 20,
            current_data=[{"feature": 10}] * 20,
        )

        payload = json.loads(result)
        assert payload["overall_status"] == "danger"
        assert payload["top_drifting_features"] == ["feature"]

    @pytest.mark.asyncio
    async def test_ab_test_design_returns_sample_size(self):
        result = await ab_test(action="design", effect_size=0.05, alpha=0.05, power=0.8)

        payload = json.loads(result)
        assert payload["n_per_group"] > 1000
