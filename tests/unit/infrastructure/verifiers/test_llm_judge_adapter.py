from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ds_agent.domain.dtos.verifier_context import EvidenceRef, VerifierConfig, VerifierContext
from ds_agent.domain.entities.messages import LLMResponse, Usage
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.domain.entities.task_contract import TaskContract
from ds_agent.infrastructure.verifiers.llm_judge_adapter import LLMNarrativeJudge

_VALID_JUDGE_JSON = (
    '{"checks": [{"check_id": "claim_evidence_alignment", "status": "pass", '
    '"score": 1.0, "message": "ok", "evidence": {}}]}'
)


def _task_contract() -> TaskContract:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    return TaskContract(
        task_id="TC-2026-001",
        session_id="session-1",
        type="churn_analysis",
        business_goal="Reduce churn",
        required_deliverables=[{"type": "exec_brief", "audience": "executive", "format": "pptx"}],
        created_at=now,
        updated_at=now,
    )


def _ctx() -> VerifierContext:
    return VerifierContext(
        run_id="run-1",
        task_contract=_task_contract(),
        artifacts={
            "analysis_mode": "churn_analysis",
            "narrative": "Accuracy improved to 0.82 and should be reviewed carefully.",
            "metrics": {"accuracy": 0.82},
            "recommendations": ["Refresh the retention dashboard."],
            "infeasible_actions": ["rewrite billing platform"],
        },
        evidence_refs=[
            EvidenceRef(
                artifact_id="artifact://metrics",
                excerpt="accuracy improved to 0.82 on the validation split",
            )
        ],
        config=VerifierConfig(),
    )


@dataclass
class FakeProvider:
    response_text: str
    model_id: str = "openai/gpt-test"
    provider_name: str = "openai"
    last_messages: list | None = None
    last_kwargs: dict[str, object] | None = None

    async def chat(self, messages, **kwargs):
        self.last_messages = messages
        self.last_kwargs = kwargs
        return LLMResponse(content=self.response_text, model=self.model_id, usage=Usage())

    async def count_tokens(self, messages) -> int:
        return 0

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_id=self.model_id,
            provider=self.provider_name,
            display_name="Test Judge",
            max_context_tokens=128_000,
            max_output_tokens=4096,
        )


def _message_snapshot(messages: list) -> list[dict[str, str | None]]:
    return [{"role": message.role.value, "content": message.content} for message in messages]


def _load_prompt_fixture(name: str) -> list[dict[str, str | None]]:
    fixture_path = (
        Path(__file__).resolve().parents[3]
        / "fixtures"
        / "verifier_judge"
        / f"{name}.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_llm_narrative_judge_parses_valid_json_code_fence() -> None:
    provider = FakeProvider(
        """```json
        {
          "checks": [
            {
              "check_id": "claim_evidence_alignment",
              "status": "pass",
              "score": 0.91,
              "message": "Claims align with the supplied evidence.",
              "evidence": {"supported_claims": 1}
            },
            {
              "check_id": "metric_citation_accuracy",
              "status": "pass",
              "score": 1.0,
              "message": "Narrative metrics match the artifact payload.",
              "evidence": {"matched_values": [0.82]}
            }
          ]
        }
        ```"""
    )

    results = await LLMNarrativeJudge(provider).evaluate(_ctx())

    assert [item.check_id for item in results] == [
        "claim_evidence_alignment",
        "metric_citation_accuracy",
    ]
    assert results[0].evidence["judge_source"] == "llm"
    assert results[0].evidence["judge_model"] == "openai/gpt-test"
    assert results[0].evidence["judge_prompt_profile"] == "openai_json"
    assert results[0].evidence["judge_prompt_version"] == "narrative_judge_v2"


def test_llm_narrative_judge_build_messages_include_schema_and_payload() -> None:
    provider = FakeProvider('{"checks": []}')
    judge = LLMNarrativeJudge(provider)

    messages = judge._build_messages(_ctx())

    assert len(messages) == 2
    assert "claim_evidence_alignment" in (messages[0].content or "")
    assert "recommendation_feasibility" in (messages[0].content or "")
    assert "Reduce churn" in (messages[1].content or "")
    assert "accuracy improved to 0.82" in (messages[1].content or "")
    assert "Prompt profile: openai_json." in (messages[0].content or "")


@pytest.mark.asyncio
async def test_llm_narrative_judge_rejects_invalid_json_payload() -> None:
    provider = FakeProvider(
        '{"checks": [{"check_id": "unknown", "status": "pass", "score": 1.0, "message": "ok"}]}'
    )

    with pytest.raises(ValueError, match="invalid JSON payload"):
        await LLMNarrativeJudge(provider).evaluate(_ctx())


@pytest.mark.asyncio
async def test_llm_narrative_judge_uses_openai_json_mode_for_direct_openai_models() -> None:
    provider = FakeProvider(
        _VALID_JUDGE_JSON,
        model_id="gpt-5.4",
        provider_name="openai",
    )

    await LLMNarrativeJudge(provider).evaluate(_ctx())

    assert provider.last_kwargs is not None
    assert provider.last_kwargs["response_format"] == {"type": "json_object"}
    assert "thinking" not in provider.last_kwargs


@pytest.mark.asyncio
async def test_llm_narrative_judge_uses_low_reasoning_effort_for_openai_reasoning_models() -> None:
    provider = FakeProvider(
        _VALID_JUDGE_JSON,
        model_id="o3",
        provider_name="openai",
    )

    await LLMNarrativeJudge(provider).evaluate(_ctx())

    assert provider.last_kwargs is not None
    assert provider.last_kwargs["response_format"] == {"type": "json_object"}
    assert provider.last_kwargs["reasoning_effort"] == "low"


@pytest.mark.asyncio
async def test_llm_narrative_judge_disables_anthropic_thinking_for_json_stability() -> None:
    provider = FakeProvider(
        _VALID_JUDGE_JSON,
        model_id="claude-sonnet-4-6",
        provider_name="anthropic",
    )

    await LLMNarrativeJudge(provider).evaluate(_ctx())

    assert provider.last_kwargs is not None
    assert provider.last_kwargs["thinking"] is False
    assert "response_format" not in provider.last_kwargs


def test_llm_narrative_judge_openai_prompt_snapshot_matches_fixture() -> None:
    provider = FakeProvider('{"checks": []}', model_id="gpt-5.4", provider_name="openai")
    judge = LLMNarrativeJudge(provider)

    messages = judge._build_messages(_ctx())

    assert _message_snapshot(messages) == _load_prompt_fixture("openai_prompt_messages")


def test_llm_narrative_judge_anthropic_prompt_snapshot_matches_fixture() -> None:
    provider = FakeProvider(
        '{"checks": []}',
        model_id="claude-sonnet-4-6",
        provider_name="anthropic",
    )
    judge = LLMNarrativeJudge(provider)

    messages = judge._build_messages(_ctx())

    assert _message_snapshot(messages) == _load_prompt_fixture("anthropic_prompt_messages")
