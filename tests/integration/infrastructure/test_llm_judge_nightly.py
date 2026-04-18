from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import pytest

from ds_agent.domain.dtos.verifier_context import EvidenceRef, VerifierConfig, VerifierContext
from ds_agent.domain.entities.messages import ChatMessage, LLMResponse
from ds_agent.domain.entities.provider_models import ModelInfo, ProviderSDKConfig
from ds_agent.domain.entities.task_contract import DeliverableSpec, TaskContract
from ds_agent.domain.interfaces.llm_provider import LLMProvider
from ds_agent.infrastructure.verifiers.llm_judge_adapter import LLMNarrativeJudge

pytestmark = [pytest.mark.integration, pytest.mark.nightly]

_ENABLE_ENV = "DS_AGENT_RUN_NIGHTLY_REAL_JUDGE"
_OPENAI_MODEL_ENV = "DS_AGENT_REAL_JUDGE_OPENAI_MODEL"
_ANTHROPIC_MODEL_ENV = "DS_AGENT_REAL_JUDGE_ANTHROPIC_MODEL"
_ENABLED_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class NightlyJudgeCase:
    name: str
    narrative: str
    analysis_mode: str
    metrics: dict[str, float]
    recommendations: list[str]
    infeasible_actions: list[str]
    evidence_excerpt: str
    expected_statuses: dict[str, set[str]]


@dataclass
class RecordingProvider(LLMProvider):
    inner: LLMProvider
    last_messages: list[ChatMessage] | None = None
    last_kwargs: dict[str, object] | None = None

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        self.last_messages = messages
        self.last_kwargs = {
            "tools": tools,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        return await self.inner.chat(
            messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            on_delta=on_delta,
            **kwargs,
        )

    async def count_tokens(self, messages: list[ChatMessage]) -> int:
        return int(await self.inner.count_tokens(messages))

    def get_model_info(self) -> ModelInfo:
        return self.inner.get_model_info()


_HEALTHY_CASE = NightlyJudgeCase(
    name="healthy_supported_narrative",
    analysis_mode="ab_test",
    narrative=(
        "The A/B experiment improved accuracy to 0.82. "
        "We should refresh the retention dashboard next."
    ),
    metrics={"accuracy": 0.82},
    recommendations=["Refresh the retention dashboard next."],
    infeasible_actions=["rewrite billing platform"],
    evidence_excerpt="accuracy improved to 0.82 in the A/B experiment validation summary",
    expected_statuses={
        "metric_citation_accuracy": {"pass"},
        "causal_language_appropriateness": {"pass"},
        "recommendation_feasibility": {"pass"},
    },
)

_VIOLATION_CASE = NightlyJudgeCase(
    name="obvious_policy_and_metric_violations",
    analysis_mode="observational_churn_analysis",
    narrative=(
        "This analysis caused churn to drop by 40%. "
        "Accuracy is 52%, so we should rewrite the billing platform immediately."
    ),
    metrics={"accuracy": 0.82},
    recommendations=["Rewrite the billing platform immediately."],
    infeasible_actions=["rewrite the billing platform immediately"],
    evidence_excerpt="accuracy improved to 0.82 on the validation split",
    expected_statuses={
        "metric_citation_accuracy": {"fail"},
        "causal_language_appropriateness": {"fail"},
        "recommendation_feasibility": {"fail"},
    },
)


def _nightly_enabled() -> bool:
    return os.getenv(_ENABLE_ENV, "").strip().lower() in _ENABLED_VALUES


def _task_contract() -> TaskContract:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    return TaskContract(
        task_id="TC-2026-001",
        session_id="session-nightly",
        type="churn_analysis",
        business_goal="Reduce churn",
        required_deliverables=[
            DeliverableSpec(type="exec_brief", audience="executive", format="pptx")
        ],
        created_at=now,
        updated_at=now,
    )


def _ctx(case: NightlyJudgeCase) -> VerifierContext:
    return VerifierContext(
        run_id=f"nightly-{case.name}",
        task_contract=_task_contract(),
        artifacts={
            "analysis_mode": case.analysis_mode,
            "narrative": case.narrative,
            "metrics": case.metrics,
            "recommendations": case.recommendations,
            "infeasible_actions": case.infeasible_actions,
        },
        evidence_refs=[
            EvidenceRef(
                artifact_id=f"artifact://{case.name}",
                excerpt=case.evidence_excerpt,
            )
        ],
        config=VerifierConfig(),
    )


def _build_provider(provider_type: Literal["openai", "anthropic"]) -> RecordingProvider:
    if provider_type == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY is required for nightly real-judge OpenAI coverage.")
        model = os.getenv(_OPENAI_MODEL_ENV, "openai/gpt-5.4")
        try:
            from ds_agent.providers.openai_provider import OpenAIProvider
        except ImportError as exc:  # pragma: no cover - environment dependent
            pytest.skip(f"OpenAI SDK is unavailable: {exc}")
        return RecordingProvider(
            OpenAIProvider(model, ProviderSDKConfig(api_key=api_key, timeout=60.0, max_retries=1))
        )

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY is required for nightly real-judge Anthropic coverage.")
    model = os.getenv(_ANTHROPIC_MODEL_ENV, "anthropic/claude-sonnet-4-6")
    try:
        from ds_agent.providers.anthropic import AnthropicProvider
    except ImportError as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Anthropic SDK is unavailable: {exc}")
    return RecordingProvider(
        AnthropicProvider(model, ProviderSDKConfig(api_key=api_key, timeout=60.0, max_retries=1))
    )


@pytest.fixture(scope="module", autouse=True)
def require_nightly_real_judge_enabled() -> None:
    if not _nightly_enabled():
        pytest.skip(
            "nightly real-judge coverage is disabled. "
            f"Set {_ENABLE_ENV}=1 to run these tests."
        )
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
        pytest.fail(
            "nightly real-judge coverage was enabled, but neither OPENAI_API_KEY nor "
            "ANTHROPIC_API_KEY is configured."
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_type", "expected_profile"),
    [
        ("openai", "openai_json"),
        ("anthropic", "anthropic_json"),
    ],
)
@pytest.mark.parametrize("case", [_HEALTHY_CASE, _VIOLATION_CASE], ids=lambda case: case.name)
async def test_real_llm_judge_nightly_provider_matrix(
    provider_type: Literal["openai", "anthropic"],
    expected_profile: str,
    case: NightlyJudgeCase,
) -> None:
    provider = _build_provider(provider_type)

    results = await LLMNarrativeJudge(provider).evaluate(_ctx(case))

    by_id = {item.check_id: item for item in results}
    for check_id, allowed_statuses in case.expected_statuses.items():
        assert check_id in by_id
        assert by_id[check_id].status in allowed_statuses
        assert by_id[check_id].evidence["judge_source"] == "llm"
        assert by_id[check_id].evidence["judge_prompt_profile"] == expected_profile
        assert by_id[check_id].evidence["judge_prompt_version"] == "narrative_judge_v2"

    assert provider.last_kwargs is not None
    if provider_type == "openai":
        assert provider.last_kwargs["response_format"] == {"type": "json_object"}
    else:
        assert provider.last_kwargs["thinking"] is False
