"""Finalize a pending learning-governance candidate into the active skill set."""

from __future__ import annotations

from pathlib import Path

from ds_agent.evaluation.application.dtos.eval_report_dto import (
    EvalBatchReport,
    ScoredRunReport,
)
from ds_agent.evaluation.domain.entities.eval_score import EvalScore
from ds_agent.evaluation.domain.entities.regression_board import (
    RegressionBoardSnapshot,
    RegressionOverallSummary,
    RegressionWindowStats,
)
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.self_improve.promotion_candidates import (
    JsonPromotionCandidateStore,
    PromotionCandidate,
)
from ds_agent.self_improve.promotion_gate import (
    CandidatePromotionDecision,
    SelfImprovePromotionGate,
)


class FinalizeLearningCandidatePromotionUseCase:
    """Apply the existing self-improve promotion gate to a learning candidate."""

    def __init__(
        self,
        workspace_dir: str | Path,
        *,
        active_custom_dir: str | Path | None = None,
    ) -> None:
        self._workspace_dir = str(Path(workspace_dir).expanduser().resolve())
        self._active_custom_dir = Path(active_custom_dir) if active_custom_dir else None
        self._candidate_store = JsonPromotionCandidateStore.for_workspace(self._workspace_dir)
        self._promotion_gate = SelfImprovePromotionGate(self._candidate_store)

    def execute(
        self,
        *,
        candidate_id: str,
        candidate_score: float,
        passed_tasks: int,
        total_tasks: int,
        baseline_score: float | None = None,
        delta_threshold: float = 0.03,
    ) -> tuple[CandidatePromotionDecision, PromotionCandidate]:
        """Finalize one pending candidate with an explicit evaluation verdict."""

        self._validate_counts(passed_tasks=passed_tasks, total_tasks=total_tasks)

        candidate = self._promotion_gate.get_candidate(candidate_id)
        if candidate.status == "promoted":
            raise ValueError(f"Candidate {candidate_id} is already promoted.")

        decision = self._promotion_gate.finalize(
            candidate_id,
            report=_manual_eval_report(
                candidate_id=candidate_id,
                candidate_score=candidate_score,
                passed_tasks=passed_tasks,
                total_tasks=total_tasks,
            ),
            baseline_snapshot=_baseline_snapshot(baseline_score),
            delta_threshold=delta_threshold,
            active_custom_dir=self._active_custom_dir,
        )
        updated = self._candidate_store.get(candidate_id)
        if updated is None:
            raise ValueError(f"Candidate {candidate_id} disappeared during promotion finalization.")
        return decision, updated

    @staticmethod
    def _validate_counts(*, passed_tasks: int, total_tasks: int) -> None:
        if total_tasks <= 0:
            raise ValueError("total_tasks must be greater than zero.")
        if passed_tasks < 0:
            raise ValueError("passed_tasks cannot be negative.")
        if passed_tasks > total_tasks:
            raise ValueError("passed_tasks cannot exceed total_tasks.")


def _manual_eval_report(
    *,
    candidate_id: str,
    candidate_score: float,
    passed_tasks: int,
    total_tasks: int,
) -> EvalBatchReport:
    task_id = f"learning-candidate:{candidate_id}"
    scored_run = ScoredRunReport(
        task_id=task_id,
        run_id=f"{candidate_id}:manual-gate",
        mode="manual_gate",
        weighted_score=candidate_score,
        passed=passed_tasks == total_tasks,
        scores={
            "manual_gate": EvalScore(
                name="manual_gate",
                value=candidate_score,
                rationale="Manual promotion gate verdict.",
                judge_type=JudgeType.DETERMINISTIC,
            )
        },
        run_metadata={"promotionCandidateId": candidate_id},
    )
    failed_tasks = total_tasks - passed_tasks
    return EvalBatchReport(
        total=total_tasks,
        passed=passed_tasks,
        failed=failed_tasks,
        per_task_scores={task_id: candidate_score},
        per_dimension_means={"manual_gate": candidate_score},
        task_reports=(scored_run,),
    )


def _baseline_snapshot(score: float | None) -> RegressionBoardSnapshot | None:
    if score is None:
        return None

    window = RegressionWindowStats(
        record_count=1,
        avg_weighted_score=score,
        pass_rate=1.0,
    )
    return RegressionBoardSnapshot(
        total_records=1,
        recent_window=1,
        baseline_window_days=14,
        overall=RegressionOverallSummary(
            recent=window,
            baseline=window,
            delta_score=0.0,
            delta_pass_rate=0.0,
        ),
    )
