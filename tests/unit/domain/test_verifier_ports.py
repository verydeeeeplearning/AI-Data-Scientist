from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.domain.dtos.verifier_context import EvidenceRef, VerifierConfig, VerifierContext
from ds_agent.domain.entities.review_verdict import (
    CheckResult,
    ConfidenceBand,
    LayerResult,
    ReviewVerdict,
)
from ds_agent.domain.entities.shadow_comparison import ShadowComparisonRecord
from ds_agent.domain.entities.task_contract import TaskContract
from ds_agent.domain.interfaces.verifier_ports import (
    ConfidenceScorerPort,
    DataCheck,
    DataVerifierPort,
    LLMJudgePort,
    NarrativeCheck,
    NarrativeVerifierPort,
    PolicyCheck,
    PolicyVerifierPort,
    ShadowComparatorPort,
    ShadowComparisonRepository,
    StatisticalCheck,
    StatisticalVerifierPort,
    VerdictRepository,
)


def _context() -> VerifierContext:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    return VerifierContext(
        run_id="run-1",
        task_contract=TaskContract(
            task_id="TC-2026-001",
            session_id="session-1",
            type="churn_analysis",
            business_goal="Reduce churn",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"}
            ],
            created_at=now,
            updated_at=now,
        ),
        evidence_refs=[EvidenceRef(artifact_id="artifact://report", excerpt="lift +2.1%")],
        config=VerifierConfig(),
    )


class _StatisticalCheckImpl:
    name = "leakage"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        return CheckResult(
            check_id="leakage",
            status="pass",
            score=1.0,
            evidence={"task_id": ctx.task_contract.task_id},
            message="clean",
            duration_ms=3,
        )


class _DataCheckImpl:
    name = "schema"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        return CheckResult(
            check_id="schema",
            status="pass",
            score=1.0,
            evidence={},
            message="ok",
            duration_ms=1,
        )


class _PolicyCheckImpl:
    name = "pii"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        return CheckResult(
            check_id="pii",
            status="pass",
            score=1.0,
            evidence={},
            message="masked",
            duration_ms=1,
        )


class _NarrativeCheckImpl:
    name = "alignment"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        return CheckResult(
            check_id="alignment",
            status="pass",
            score=1.0,
            evidence={},
            message="supported",
            duration_ms=1,
        )


class _StatisticalVerifierImpl:
    async def run(self, ctx: VerifierContext) -> LayerResult:
        return LayerResult(layer="statistical")


class _DataVerifierImpl:
    async def run(self, ctx: VerifierContext) -> LayerResult:
        return LayerResult(layer="data")


class _PolicyVerifierImpl:
    async def run(self, ctx: VerifierContext) -> LayerResult:
        return LayerResult(layer="policy")


class _NarrativeVerifierImpl:
    async def run(self, ctx: VerifierContext) -> LayerResult:
        return LayerResult(layer="narrative")


class _LLMJudgeImpl:
    async def evaluate(self, ctx: VerifierContext) -> list[CheckResult]:
        return [
            CheckResult(
                check_id="claim_evidence_alignment",
                status="pass",
                score=1.0,
                evidence={},
                message="aligned",
                duration_ms=1,
            )
        ]


class _VerdictRepositoryImpl:
    def save(self, verdict: ReviewVerdict) -> None:
        self.saved = verdict

    def get(self, verdict_id: str) -> ReviewVerdict | None:
        return None

    def list_for_task(self, task_id: str) -> list[ReviewVerdict]:
        return []


class _ConfidenceScorerImpl:
    def score(self, verdict: ReviewVerdict) -> ConfidenceBand:
        return ConfidenceBand(score=0.88, rationale="clean")

    def explain(self, verdict: ReviewVerdict) -> str:
        return "clean"


class _ShadowComparatorImpl:
    def compare(
        self,
        ctx: VerifierContext,
        verdict: ReviewVerdict,
    ) -> ShadowComparisonRecord | None:
        return None


class _ShadowComparisonRepositoryImpl:
    def save(self, record: ShadowComparisonRecord) -> None:
        self.saved = record

    def get(self, comparison_id: str) -> ShadowComparisonRecord | None:
        return None

    def list_for_task(self, task_id: str) -> list[ShadowComparisonRecord]:
        return []

    def list_for_verdict(self, verdict_id: str) -> list[ShadowComparisonRecord]:
        return []


def test_verifier_ports_are_runtime_checkable() -> None:
    ctx = _context()

    statistical_check = _StatisticalCheckImpl()
    data_check = _DataCheckImpl()
    policy_check = _PolicyCheckImpl()
    narrative_check = _NarrativeCheckImpl()

    assert isinstance(statistical_check, StatisticalCheck)
    assert isinstance(data_check, DataCheck)
    assert isinstance(policy_check, PolicyCheck)
    assert isinstance(narrative_check, NarrativeCheck)
    assert statistical_check.run(ctx).check_id == "leakage"

    assert isinstance(_StatisticalVerifierImpl(), StatisticalVerifierPort)
    assert isinstance(_DataVerifierImpl(), DataVerifierPort)
    assert isinstance(_PolicyVerifierImpl(), PolicyVerifierPort)
    assert isinstance(_NarrativeVerifierImpl(), NarrativeVerifierPort)
    assert isinstance(_LLMJudgeImpl(), LLMJudgePort)
    assert isinstance(_VerdictRepositoryImpl(), VerdictRepository)
    assert isinstance(_ConfidenceScorerImpl(), ConfidenceScorerPort)
    assert isinstance(_ShadowComparatorImpl(), ShadowComparatorPort)
    assert isinstance(_ShadowComparisonRepositoryImpl(), ShadowComparisonRepository)
