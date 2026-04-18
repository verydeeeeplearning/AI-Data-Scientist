"""Problem type router hook tests for PLAN 17 Phase 6."""

from __future__ import annotations

import pytest

from ds_agent.agent.builtin_hooks import ProblemTypeRouterHook
from ds_agent.agent.hooks import HookContext


class TestProblemTypeRouterHook:
    @pytest.mark.asyncio
    async def test_injects_analysis_type_guidance(self):
        hook = ProblemTypeRouterHook()
        events: list[tuple[str, dict]] = []
        ctx = HookContext(
            emit=lambda event, payload: events.append((event, payload)),
            user_message="다음 달 매출 예측해줘",
        )

        text = await hook.on_session_init(ctx)

        assert text is not None
        assert "forecasting" in text
        assert events[0][0] == "analysis_type.detected"
