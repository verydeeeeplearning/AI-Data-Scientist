from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from ds_agent.agent.confidence_scorer import ConfidenceScorer
from ds_agent.application.services.verifier_orchestrator import VerifierOrchestrator
from ds_agent.domain.dtos.verifier_context import VerifierConfig, VerifierContext
from ds_agent.domain.entities.review_verdict import CheckResult, LayerResult, ReviewVerdict
from ds_agent.domain.entities.shadow_comparison import ShadowComparisonRecord
from ds_agent.domain.entities.task_contract import TaskContract


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


def _ctx(config: VerifierConfig | None = None) -> VerifierContext:
    return VerifierContext(
        run_id="run-1",
        task_contract=_task_contract(),
        artifacts={},
        config=config or VerifierConfig(),
    )


@dataclass
class FixedClock:
    now_value: datetime = datetime(2026, 4, 16, tzinfo=UTC)

    def now(self) -> datetime:
        return self.now_value


class InMemoryRepo:
    def __init__(self) -> None:
        self.saved: list[ReviewVerdict] = []

    def save(self, verdict: ReviewVerdict) -> None:
        self.saved.append(verdict)

    def get(self, verdict_id: str) -> ReviewVerdict | None:
        for verdict in self.saved:
            if verdict.verdict_id == verdict_id:
                return verdict
        return None

    def list_for_task(self, task_id: str) -> list[ReviewVerdict]:
        return [verdict for verdict in self.saved if verdict.task_id == task_id]


class InMemoryShadowRepo:
    def __init__(self) -> None:
        self.saved: list[ShadowComparisonRecord] = []

    def save(self, record: ShadowComparisonRecord) -> None:
        self.saved.append(record)

    def get(self, comparison_id: str) -> ShadowComparisonRecord | None:
        for record in self.saved:
            if record.comparison_id == comparison_id:
                return record
        return None

    def list_for_task(self, task_id: str) -> list[ShadowComparisonRecord]:
        return [record for record in self.saved if record.task_id == task_id]

    def list_for_verdict(self, verdict_id: str) -> list[ShadowComparisonRecord]:
        return [record for record in self.saved if record.verdict_id == verdict_id]


class StaticVerifier:
    def __init__(self, layer_result: LayerResult) -> None:
        self._layer_result = layer_result

    async def run(self, ctx: VerifierContext) -> LayerResult:
        return self._layer_result


class SlowVerifier:
    def __init__(self, layer: str, delay_seconds: float) -> None:
        self._layer = layer
        self._delay_seconds = delay_seconds

    async def run(self, ctx: VerifierContext) -> LayerResult:
        await asyncio.sleep(self._delay_seconds)
        return LayerResult(layer=self._layer)  # type: ignore[arg-type]


class StaticShadowComparator:
    def compare(
        self,
        ctx: VerifierContext,
        verdict: ReviewVerdict,
    ) -> ShadowComparisonRecord | None:
        return ShadowComparisonRecord(
            comparison_id="SC-2026001",
            verdict_id=verdict.verdict_id,
            task_id=verdict.task_id,
            run_id=verdict.run_id,
            session_id=ctx.task_contract.session_id,
            created_at=verdict.created_at,
            items=[],
            metadata={"source": "test"},
        )


def _layer(layer: str, status: str, score: float, message: str) -> LayerResult:
    return LayerResult(
        layer=layer,  # type: ignore[arg-type]
        checks=[
            CheckResult(
                check_id=f"{layer}_check",
                status=status,  # type: ignore[arg-type]
                score=score,
                evidence={},
                message=message,
                duration_ms=1,
            )
        ],
    )


@pytest.mark.asyncio
async def test_orchestrator_aggregates_layers_scores_and_persists_verdict() -> None:
    repo = InMemoryRepo()
    orchestrator = VerifierOrchestrator(
        statistical=StaticVerifier(_layer("statistical", "pass", 1.0, "stable")),
        data=StaticVerifier(_layer("data", "warn", 0.55, "drift detected")),
        policy=StaticVerifier(_layer("policy", "fail", 0.0, "pii detected")),
        narrative=StaticVerifier(_layer("narrative", "pass", 1.0, "aligned")),
        repo=repo,
        scorer=ConfidenceScorer(),
        clock=FixedClock(),
    )

    verdict = await orchestrator.run(_ctx())

    assert verdict.overall == "fail"
    assert verdict.confidence is not None
    assert verdict.confidence.grade in {"low", "insufficient", "medium"}
    assert verdict.blocking_issues
    assert verdict.recommended_actions
    assert repo.saved[-1].verdict_id == verdict.verdict_id


@pytest.mark.asyncio
async def test_orchestrator_converts_timeout_into_error_layer() -> None:
    repo = InMemoryRepo()
    orchestrator = VerifierOrchestrator(
        statistical=StaticVerifier(_layer("statistical", "pass", 1.0, "stable")),
        data=StaticVerifier(_layer("data", "pass", 1.0, "clean")),
        policy=StaticVerifier(_layer("policy", "pass", 1.0, "safe")),
        narrative=SlowVerifier("narrative", delay_seconds=1.1),
        repo=repo,
        scorer=ConfidenceScorer(),
        clock=FixedClock(),
    )

    verdict = await orchestrator.run(_ctx(VerifierConfig(narrative_timeout_s=1)))
    narrative_layer = next(layer for layer in verdict.layers if layer.layer == "narrative")

    assert narrative_layer.overall == "error"
    assert narrative_layer.partial_failure is True
    assert verdict.overall == "fail"
    assert repo.saved


@pytest.mark.asyncio
async def test_orchestrator_persists_shadow_comparison_when_enabled() -> None:
    repo = InMemoryRepo()
    shadow_repo = InMemoryShadowRepo()
    orchestrator = VerifierOrchestrator(
        statistical=StaticVerifier(_layer("statistical", "pass", 1.0, "stable")),
        data=StaticVerifier(_layer("data", "pass", 1.0, "clean")),
        policy=StaticVerifier(_layer("policy", "pass", 1.0, "safe")),
        narrative=StaticVerifier(_layer("narrative", "pass", 1.0, "aligned")),
        repo=repo,
        scorer=ConfidenceScorer(),
        clock=FixedClock(),
        shadow_comparator=StaticShadowComparator(),
        shadow_repo=shadow_repo,
    )

    verdict = await orchestrator.run(_ctx(VerifierConfig(shadow_mode=True)))

    assert shadow_repo.saved
    assert verdict.metadata["shadow_comparison_id"] == "SC-2026001"
    assert verdict.metadata["shadow_mismatch_count"] == 0


@pytest.mark.asyncio
async def test_orchestrator_promotes_narrative_judge_metadata_to_verdict() -> None:
    repo = InMemoryRepo()
    orchestrator = VerifierOrchestrator(
        statistical=StaticVerifier(_layer("statistical", "pass", 1.0, "stable")),
        data=StaticVerifier(_layer("data", "pass", 1.0, "clean")),
        policy=StaticVerifier(_layer("policy", "pass", 1.0, "safe")),
        narrative=StaticVerifier(
            LayerResult(
                layer="narrative",
                checks=[
                    CheckResult(
                        check_id="claim_evidence_alignment",
                        status="pass",
                        score=1.0,
                        evidence={},
                        message="aligned",
                        duration_ms=1,
                    )
                ],
                metadata={"judge_mode": "llm", "judge_check_count": 2},
            )
        ),
        repo=repo,
        scorer=ConfidenceScorer(),
        clock=FixedClock(),
    )

    verdict = await orchestrator.run(_ctx())

    assert verdict.metadata["judge_mode"] == "llm"
    assert verdict.metadata["judge_check_count"] == 2
