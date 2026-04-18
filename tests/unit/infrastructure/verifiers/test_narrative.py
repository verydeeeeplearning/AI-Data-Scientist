from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ds_agent.domain.dtos.verifier_context import EvidenceRef, VerifierConfig, VerifierContext
from ds_agent.domain.entities.review_verdict import CheckResult
from ds_agent.domain.entities.task_contract import TaskContract
from ds_agent.infrastructure.verifiers.narrative import NarrativeVerifier


def _task_contract(task_type: str = "churn_analysis") -> TaskContract:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    return TaskContract(
        task_id="TC-2026-001",
        session_id="session-1",
        type=task_type,
        business_goal="Reduce churn",
        required_deliverables=[{"type": "exec_brief", "audience": "executive", "format": "pptx"}],
        created_at=now,
        updated_at=now,
    )


def _ctx(
    *,
    narrative: str,
    evidence_refs: list[EvidenceRef] | None = None,
    task_type: str = "churn_analysis",
    artifacts: dict[str, object] | None = None,
) -> VerifierContext:
    merged = {"narrative": narrative}
    if artifacts:
        merged.update(artifacts)
    return VerifierContext(
        run_id="run-1",
        task_contract=_task_contract(task_type),
        artifacts=merged,
        evidence_refs=evidence_refs or [],
        config=VerifierConfig(),
    )


def _find_check(result, check_id: str) -> CheckResult:
    return next(check for check in result.checks if check.check_id == check_id)


class _JudgeResult:
    def __init__(self, checks: list[CheckResult]) -> None:
        self._checks = checks

    async def evaluate(self, ctx: VerifierContext) -> list[CheckResult]:
        return self._checks


class _BrokenJudge:
    async def evaluate(self, ctx: VerifierContext) -> list[CheckResult]:
        raise ValueError("malformed judge response")


@pytest.mark.asyncio
async def test_claim_evidence_alignment_fails_for_unsupported_claims() -> None:
    result = await NarrativeVerifier().run(
        _ctx(
            narrative="Revenue will double next month. Conversion improved by 12%.",
            evidence_refs=[
                EvidenceRef(
                    artifact_id="artifact://metrics",
                    excerpt="conversion improved by 12%",
                )
            ],
        )
    )

    check = _find_check(result, "claim_evidence_alignment")

    assert check.status == "fail"


@pytest.mark.asyncio
async def test_causal_language_fails_for_non_experimental_task() -> None:
    result = await NarrativeVerifier().run(
        _ctx(narrative="This campaign causes churn to drop by 10%.")
    )

    check = _find_check(result, "causal_language_appropriateness")

    assert check.status == "fail"


@pytest.mark.asyncio
async def test_metric_citation_accuracy_fails_on_mismatched_numbers() -> None:
    result = await NarrativeVerifier().run(
        _ctx(
            narrative="Accuracy reached 0.91.",
            artifacts={"metrics": {"accuracy": 0.82}},
        )
    )

    check = _find_check(result, "metric_citation_accuracy")

    assert check.status == "fail"


@pytest.mark.asyncio
async def test_recommendation_feasibility_fails_when_recommendation_is_out_of_scope() -> None:
    result = await NarrativeVerifier().run(
        _ctx(
            narrative="Recommend a full database rewrite.",
            artifacts={
                "recommendations": ["Do a full database rewrite."],
                "infeasible_actions": ["database rewrite"],
            },
        )
    )

    check = _find_check(result, "recommendation_feasibility")

    assert check.status == "fail"


@pytest.mark.asyncio
async def test_narrative_verifier_prefers_llm_judge_results_when_available() -> None:
    result = await NarrativeVerifier(
        judge=_JudgeResult(
            [
                CheckResult(
                    check_id="claim_evidence_alignment",
                    status="warn",
                    score=0.4,
                    evidence={"judge_source": "llm"},
                    message="LLM judge found a weak claim.",
                    duration_ms=5,
                )
            ]
        )
    ).run(
        _ctx(
            narrative="Conversion improved by 12%.",
            evidence_refs=[
                EvidenceRef(
                    artifact_id="artifact://metrics",
                    excerpt="conversion improved by 12%",
                )
            ],
        )
    )

    check = _find_check(result, "claim_evidence_alignment")

    assert check.status == "warn"
    assert result.metadata["judge_mode"] == "llm"


@pytest.mark.asyncio
async def test_narrative_verifier_falls_back_to_heuristics_when_judge_fails() -> None:
    result = await NarrativeVerifier(judge=_BrokenJudge()).run(
        _ctx(
            narrative="Revenue will double next month.",
            evidence_refs=[],
        )
    )

    check = _find_check(result, "claim_evidence_alignment")

    assert check.status == "fail"
    assert result.metadata["judge_mode"] == "heuristic_fallback"
    assert result.metadata["judge_error"] == "ValueError"
