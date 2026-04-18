"""Subagent orchestration tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ds_agent.application.services.subagent_orchestrator import SubagentOrchestrator
from ds_agent.domain.entities.messages import LLMResponse, Usage
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.domain.value_objects.budget import BudgetPolicy
from ds_agent.domain.value_objects.subagent import SubagentSpec
from ds_agent.infrastructure.process_subagent import ProcessSubagent


def _make_provider_factory(response_builder):
    def _factory(model_name: str | None):
        resolved_model = model_name or "gpt-5.4-mini"
        provider = MagicMock()

        async def _chat(
            messages,
            tools=None,
            temperature=0.0,
            max_tokens=None,
            on_delta=None,
            **kwargs,
        ):
            prompt = messages[-1].content or ""
            content, usage = response_builder(prompt, resolved_model)
            return LLMResponse(content=content, usage=usage, model=resolved_model)

        provider.chat = AsyncMock(side_effect=_chat)
        provider.count_tokens = AsyncMock(return_value=256)
        provider.get_model_info = MagicMock(
            return_value=ModelInfo(
                model_id=resolved_model,
                provider="mock",
                display_name="Mock",
                max_context_tokens=128_000,
                max_output_tokens=4096,
            )
        )
        return provider

    return _factory


def _make_tool_registry():
    registry = MagicMock()
    registry.get_definitions.return_value = []
    registry.dispatch = AsyncMock(return_value="{}")
    return registry


class TestSubagentOrchestration:
    @pytest.mark.asyncio
    async def test_subagent_spawn_and_execute(self):
        executor = ProcessSubagent(
            provider_factory=_make_provider_factory(
                lambda prompt, model: (
                    "검증 완료: 방법론 오류 없음.",
                    Usage(input_tokens=120, output_tokens=45),
                )
            ),
            tool_registry=_make_tool_registry(),
            workspace_dir="C:/workspace",
        )
        orchestrator = SubagentOrchestrator(executor=executor)

        result = await orchestrator.spawn_and_wait(
            SubagentSpec(role="validator", prompt="검증해줘"),
            context_summary="모델 초안: XGBoost baseline",
            parent_session_id="session-main",
            parent_model="gpt-5.4-mini",
        )

        assert result.status == "completed"
        assert "검증 완료" in result.output
        assert result.session_id.startswith("session-main:subagent:validator:")

    @pytest.mark.asyncio
    async def test_builder_validator_feedback_loop(self):
        def response_builder(prompt: str, model: str):
            if "Subagent role: validator" in prompt:
                return (
                    "검증 결과: 누수는 없지만 tenure 인코딩 보완이 필요합니다.",
                    Usage(input_tokens=100, output_tokens=40),
                )
            if "Feedback:" in prompt:
                return (
                    "수정본: tenure 인코딩을 ordinal bucket으로 보완했습니다.",
                    Usage(input_tokens=130, output_tokens=60),
                )
            return (
                "초안: churn baseline 모델과 핵심 feature importance를 정리했습니다.",
                Usage(input_tokens=110, output_tokens=55),
            )

        executor = ProcessSubagent(
            provider_factory=_make_provider_factory(response_builder),
            tool_registry=_make_tool_registry(),
        )
        orchestrator = SubagentOrchestrator(executor=executor)

        builder = await orchestrator.spawn_and_wait(
            SubagentSpec(role="builder", prompt="이탈 예측 초안을 작성해줘"),
            context_summary="문제: telecom churn",
            parent_session_id="session-1",
        )
        validator = await orchestrator.spawn_and_wait(
            SubagentSpec(role="validator", prompt="builder 결과를 검증해줘"),
            context_summary=builder.output,
            parent_session_id="session-1",
        )
        revision = await orchestrator.spawn_and_wait(
            SubagentSpec(role="builder", prompt="validator 피드백을 반영해 수정해줘"),
            context_summary=f"{builder.output}\n\nFeedback:\n{validator.output}",
            parent_session_id="session-1",
        )

        assert "초안" in builder.output
        assert "검증 결과" in validator.output
        assert "수정본" in revision.output

    @pytest.mark.asyncio
    async def test_subagent_budget_isolation(self):
        main_budget = BudgetPolicy(max_iterations=25, max_cost_usd=8.0)
        executor = ProcessSubagent(
            provider_factory=_make_provider_factory(
                lambda prompt, model: (
                    "비용이 큰 검증을 수행했습니다.",
                    Usage(input_tokens=250_000, output_tokens=80_000),
                )
            ),
            tool_registry=_make_tool_registry(),
            default_budget_policy=main_budget,
        )
        orchestrator = SubagentOrchestrator(executor=executor)

        result = await orchestrator.spawn_and_wait(
            SubagentSpec(
                role="validator",
                prompt="고비용 검증을 실행해줘",
                budget_usd=0.05,
                model="gpt-5.4",
            ),
            parent_session_id="session-budget",
        )

        assert result.budget_summary["max_cost_usd"] == 0.05
        assert bool(result.budget_summary["is_exhausted"]) is True
        assert main_budget.max_cost_usd == 8.0

    @pytest.mark.asyncio
    async def test_parallel_subagents_return_results_in_input_order(self):
        def response_builder(prompt: str, model: str):
            if "Subagent role: reporter" in prompt:
                return (
                    "리포트 요약: KPI 변동과 리스크를 정리했습니다.",
                    Usage(input_tokens=90, output_tokens=35),
                )
            return (
                "운영 점검: 배치 지연과 알람 상태를 확인했습니다.",
                Usage(input_tokens=85, output_tokens=30),
            )

        executor = ProcessSubagent(
            provider_factory=_make_provider_factory(response_builder),
            tool_registry=_make_tool_registry(),
        )
        orchestrator = SubagentOrchestrator(executor=executor)

        specs = [
            SubagentSpec(role="reporter", prompt="분석 결과를 임원용으로 요약해줘"),
            SubagentSpec(role="operator", prompt="운영 이상 여부를 점검해줘"),
        ]

        results = await orchestrator.spawn_parallel(
            specs,
            context_summary="주간 KPI와 배치 로그 요약",
            parent_session_id="session-parallel",
        )

        merged = "\n".join(result.output for result in results)

        assert [result.spec.role for result in results] == ["reporter", "operator"]
        assert "리포트 요약" in merged
        assert "운영 점검" in merged
