from __future__ import annotations

from pathlib import Path

from ds_agent.evaluation.application.dtos.eval_report_dto import EvalBatchReport, ScoredRunReport
from ds_agent.evaluation.domain.entities.eval_score import EvalScore
from ds_agent.evaluation.domain.entities.regression_board import (
    RegressionBoardSnapshot,
    RegressionOverallSummary,
    RegressionWindowStats,
)
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.self_improve.promotion_candidates import JsonPromotionCandidateStore
from ds_agent.self_improve.promotion_gate import SelfImprovePromotionGate


def _batch_report(weighted_score: float, *, passed: bool = True) -> EvalBatchReport:
    report = ScoredRunReport(
        task_id="retail.alpha.v1",
        run_id="run-001",
        mode="offline",
        weighted_score=weighted_score,
        passed=passed,
        scores={
            "scoping_accuracy": EvalScore(
                name="scoping_accuracy",
                value=weighted_score,
                rationale="fixture",
                judge_type=JudgeType.LLM,
            )
        },
    )
    return EvalBatchReport(
        total=1,
        passed=1 if passed else 0,
        failed=0 if passed else 1,
        per_task_scores={report.task_id: report.weighted_score},
        per_dimension_means={"scoping_accuracy": weighted_score},
        task_reports=(report,),
    )


def _baseline_snapshot(weighted_score: float) -> RegressionBoardSnapshot:
    window = RegressionWindowStats(
        record_count=4,
        avg_weighted_score=weighted_score,
        pass_rate=1.0,
    )
    return RegressionBoardSnapshot(
        total_records=4,
        recent_window=3,
        baseline_window_days=14,
        overall=RegressionOverallSummary(
            recent=window,
            baseline=window,
            delta_score=0.0,
            delta_pass_rate=0.0,
        ),
    )


def test_promotion_gate_promotes_candidate_within_threshold(tmp_path: Path) -> None:
    pending_dir = tmp_path / "pending"
    pending_dir.mkdir()
    pending_path = pending_dir / "candidate.md"
    pending_path.write_text(
        "---\n"
        "name: candidate\n"
        "description: pending skill\n"
        "category: extracted\n"
        'tags: ["extracted"]\n'
        "---\n\n# Candidate\n",
        encoding="utf-8",
    )
    store = JsonPromotionCandidateStore(tmp_path / "promotion_candidates.json")
    candidate = store.register_skill_candidate(
        candidate_id="candidate-001",
        name="candidate",
        description="pending skill",
        source_project_id="proj-001",
        pending_path=pending_path,
    )
    gate = SelfImprovePromotionGate(store)

    decision = gate.finalize(
        candidate.candidate_id,
        report=_batch_report(0.79),
        baseline_snapshot=_baseline_snapshot(0.80),
        delta_threshold=0.03,
        active_custom_dir=tmp_path / "custom",
    )

    promoted = store.get(candidate.candidate_id)
    assert decision.promoted is True
    assert decision.status == "promoted"
    assert promoted is not None
    assert promoted.status == "promoted"
    assert promoted.promoted_path is not None
    assert Path(promoted.promoted_path).exists()


def test_promotion_gate_blocks_candidate_when_regressed(tmp_path: Path) -> None:
    pending_dir = tmp_path / "pending"
    pending_dir.mkdir()
    pending_path = pending_dir / "candidate.md"
    pending_path.write_text(
        "---\n"
        "name: candidate\n"
        "description: pending skill\n"
        "category: extracted\n"
        'tags: ["extracted"]\n'
        "---\n\n# Candidate\n",
        encoding="utf-8",
    )
    store = JsonPromotionCandidateStore(tmp_path / "promotion_candidates.json")
    candidate = store.register_skill_candidate(
        candidate_id="candidate-002",
        name="candidate",
        description="pending skill",
        source_project_id="proj-001",
        pending_path=pending_path,
    )
    gate = SelfImprovePromotionGate(store)

    decision = gate.finalize(
        candidate.candidate_id,
        report=_batch_report(0.70),
        baseline_snapshot=_baseline_snapshot(0.80),
        delta_threshold=0.03,
        active_custom_dir=tmp_path / "custom",
    )

    blocked = store.get(candidate.candidate_id)
    assert decision.promoted is False
    assert decision.status == "blocked"
    assert blocked is not None
    assert blocked.status == "blocked"
    assert blocked.promoted_path is None
