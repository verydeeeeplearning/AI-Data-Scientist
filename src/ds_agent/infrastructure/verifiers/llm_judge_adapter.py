"""Provider-backed narrative judge with strict JSON validation."""

from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ds_agent.domain.dtos.verifier_context import VerifierContext
from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.domain.entities.review_verdict import CheckResult
from ds_agent.domain.interfaces.llm_provider import LLMProvider
from ds_agent.domain.interfaces.verifier_ports import LLMJudgePort
from ds_agent.infrastructure.verifiers.common import artifact, elapsed_ms

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.IGNORECASE | re.DOTALL)
_PROMPT_VERSION = "narrative_judge_v2"
_ALLOWED_CHECK_IDS = (
    "claim_evidence_alignment",
    "overstatement_hedge_detection",
    "causal_language_appropriateness",
    "metric_citation_accuracy",
    "recommendation_feasibility",
)


class _NarrativeJudgeCheckPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: Literal[
        "claim_evidence_alignment",
        "overstatement_hedge_detection",
        "causal_language_appropriateness",
        "metric_citation_accuracy",
        "recommendation_feasibility",
    ]
    status: Literal["pass", "warn", "fail", "skipped", "error"]
    score: float = Field(ge=0.0, le=1.0)
    message: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    remediation_hint: str | None = None


class _NarrativeJudgeResponsePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checks: list[_NarrativeJudgeCheckPayload] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def _validate_unique_check_ids(self) -> _NarrativeJudgeResponsePayload:
        check_ids = [item.check_id for item in self.checks]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("narrative judge returned duplicate check ids")
        return self


class LLMNarrativeJudge(LLMJudgePort):
    """Ask the active provider to score narrative checks with strict JSON output."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        temperature: float = 0.0,
        max_tokens: int = 900,
    ) -> None:
        self._provider = provider
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def evaluate(self, ctx: VerifierContext) -> list[CheckResult]:
        started = perf_counter()
        model_info = self._provider.get_model_info()
        prompt_profile = self._prompt_profile(model_info)
        provider_chat = cast(Any, self._provider).chat
        response = await provider_chat(
            self._build_messages(ctx, prompt_profile=prompt_profile),
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            **self._chat_kwargs(model_info),
        )
        payload = self._parse_response_payload(response.content)
        duration_ms = elapsed_ms(started)
        judge_model = response.model or model_info.model_id
        return [
            CheckResult(
                check_id=item.check_id,
                status=item.status,
                score=item.score,
                evidence={
                    **item.evidence,
                    "judge_source": "llm",
                    "judge_model": judge_model,
                    "judge_prompt_profile": prompt_profile,
                    "judge_prompt_version": _PROMPT_VERSION,
                },
                message=item.message,
                remediation_hint=item.remediation_hint,
                duration_ms=duration_ms,
            )
            for item in payload.checks
        ]

    def _build_messages(
        self,
        ctx: VerifierContext,
        *,
        prompt_profile: str | None = None,
    ) -> list[ChatMessage]:
        profile = prompt_profile or self._prompt_profile(self._provider.get_model_info())
        system_prompt = (
            "You are the DS Agent narrative judge. "
            "Return only one JSON object with a `checks` array. "
            "Do not add markdown, commentary, or code fences unless the caller already asked. "
            "Evaluate exactly these check ids when applicable: "
            + ", ".join(_ALLOWED_CHECK_IDS)
            + ". "
            "Allowed statuses: pass, warn, fail, skipped, error. "
            "Each check needs: check_id, status, score(0..1), message, evidence(object), "
            "remediation_hint(optional). "
            "Use `skipped` only when the required input artifact is missing. "
            f"Prompt profile: {profile}. "
            + self._profile_instruction(profile)
        )
        user_payload = {
            "task_contract": {
                "task_id": ctx.task_contract.task_id,
                "task_type": ctx.task_contract.type,
                "business_goal": ctx.task_contract.business_goal,
            },
            "analysis_mode": artifact(ctx, "analysis_mode", default=ctx.task_contract.type),
            "narrative": str(artifact(ctx, "narrative", default="") or ""),
            "metrics": self._scalar_metrics(ctx),
            "recommendations": self._string_list(artifact(ctx, "recommendations", default=[])),
            "infeasible_actions": self._string_list(
                artifact(ctx, "infeasible_actions", default=[])
            ),
            "evidence_refs": [
                {
                    "artifact_id": ref.artifact_id,
                    "excerpt": (ref.excerpt or "")[:280],
                }
                for ref in ctx.evidence_refs[:8]
            ],
        }
        user_prompt = (
            "Score the narrative review checks using only the supplied payload. "
            "Be skeptical, prefer fail/warn over unsupported pass, and keep messages concise.\n\n"
            + json.dumps(user_payload, ensure_ascii=False, indent=2)
        )
        return [
            ChatMessage(role=Role.SYSTEM, content=system_prompt),
            ChatMessage(role=Role.USER, content=user_prompt),
        ]

    @staticmethod
    def _scalar_metrics(ctx: VerifierContext) -> dict[str, float]:
        metrics = artifact(ctx, "metrics", default={})
        if not isinstance(metrics, dict):
            return {}
        return {
            str(key): float(value)
            for key, value in metrics.items()
            if isinstance(value, (int, float))
        }

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    @staticmethod
    def _prompt_profile(model_info: ModelInfo) -> str:
        provider = model_info.provider.lower()
        model_id = model_info.model_id.lower()
        if provider == "anthropic" or model_id.startswith("claude"):
            return "anthropic_json"
        if provider == "openai" or model_id.startswith(("gpt-", "o1", "o3", "o4")):
            return "openai_json"
        return "generic_json"

    @staticmethod
    def _profile_instruction(profile: str) -> str:
        if profile == "anthropic_json":
            return (
                "Anthropic profile: start directly with `{`, avoid any preamble, "
                "and keep output compact so no thinking-style prose appears."
            )
        if profile == "openai_json":
            return (
                "OpenAI profile: strict JSON mode, start at the opening brace and end "
                "at the final closing brace."
            )
        return "Generic profile: emit a single compact JSON object and nothing else."

    @staticmethod
    def _chat_kwargs(model_info: ModelInfo) -> dict[str, object]:
        provider = model_info.provider.lower()
        model_id = model_info.model_id.lower()
        if provider == "anthropic" or model_id.startswith("claude"):
            return {"thinking": False}
        if provider == "openai" or model_id.startswith(("gpt-", "o1", "o3", "o4")):
            kwargs: dict[str, object] = {"response_format": {"type": "json_object"}}
            if model_id.startswith(("o1", "o3", "o4")):
                kwargs["reasoning_effort"] = "low"
            return kwargs
        return {}

    @staticmethod
    def _parse_response_payload(content: str | None) -> _NarrativeJudgeResponsePayload:
        if not content or not content.strip():
            raise ValueError("narrative judge returned empty content")

        candidates: list[str] = [content.strip()]
        fenced = _FENCED_JSON_RE.search(content)
        if fenced:
            candidates.insert(0, fenced.group(1).strip())

        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and start < end:
            candidates.append(content[start : end + 1].strip())

        errors: list[str] = []
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                return _NarrativeJudgeResponsePayload.model_validate(parsed)
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
                errors.append(str(exc))

        raise ValueError("narrative judge returned invalid JSON payload: " + "; ".join(errors[:3]))
