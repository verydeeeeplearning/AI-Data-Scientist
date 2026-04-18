from __future__ import annotations

from ds_agent.evaluation.application.use_cases.build_regression_board import (
    BuildRegressionBoard,
    FreezeRegressionBaseline,
)
from ds_agent.evaluation.domain.entities.eval_score import EvalDatasetRecord, EvalScore
from ds_agent.evaluation.domain.entities.regression_board import RegressionBoardBaseline
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType


def _record(
    *,
    task_id: str,
    run_id: str,
    recorded_at: float,
    weighted_score: float,
    passed: bool,
    scoping: float,
    mode: str = "offline",
) -> EvalDatasetRecord:
    return EvalDatasetRecord(
        recorded_at=recorded_at,
        task_id=task_id,
        run_id=run_id,
        mode=mode,
        weighted_score=weighted_score,
        passed=passed,
        scores={
            "scoping_accuracy": EvalScore(
                name="scoping_accuracy",
                value=scoping,
                rationale="fixture",
                judge_type=JudgeType.LLM,
            )
        },
        run_metadata={
            "taskDomain": "retail",
            "taskDifficulty": "medium",
        },
    )


class _MemoryEvalStore:
    def __init__(self, records: list[EvalDatasetRecord]) -> None:
        self._records = list(records)

    def append(self, record: EvalDatasetRecord) -> None:
        self._records.append(record)

    def load_all(self) -> list[EvalDatasetRecord]:
        return list(self._records)


class _MemoryBaselineStore:
    def __init__(self, baseline: RegressionBoardBaseline | None = None) -> None:
        self._baseline = baseline

    def save(self, baseline: RegressionBoardBaseline) -> None:
        self._baseline = baseline

    def load_latest(self) -> RegressionBoardBaseline | None:
        return self._baseline


def test_build_regression_board_uses_frozen_baseline_for_alerts() -> None:
    records = [
        _record(
            task_id="retail.alpha.v1",
            run_id="run-1",
            recorded_at=1_700_000_000.0,
            weighted_score=0.95,
            passed=True,
            scoping=0.93,
        ),
        _record(
            task_id="retail.beta.v1",
            run_id="run-2",
            recorded_at=1_700_000_010.0,
            weighted_score=0.94,
            passed=True,
            scoping=0.92,
        ),
        _record(
            task_id="retail.alpha.v1",
            run_id="run-3",
            recorded_at=1_700_086_400.0,
            weighted_score=0.88,
            passed=True,
            scoping=0.88,
        ),
        _record(
            task_id="retail.beta.v1",
            run_id="run-4",
            recorded_at=1_700_172_800.0,
            weighted_score=0.58,
            passed=False,
            scoping=0.80,
        ),
        _record(
            task_id="retail.alpha.v1",
            run_id="run-5",
            recorded_at=1_700_259_200.0,
            weighted_score=0.55,
            passed=False,
            scoping=0.79,
            mode="online",
        ),
        _record(
            task_id="retail.beta.v1",
            run_id="run-6",
            recorded_at=1_700_259_210.0,
            weighted_score=0.76,
            passed=True,
            scoping=0.81,
        ),
    ]
    baseline = RegressionBoardBaseline(
        baseline_id="baseline-123",
        commit_sha="stable-commit",
        mode=None,
        domain=None,
        pass_rate=0.95,
        weighted_score_mean=0.92,
        source_point_count=8,
        dimension_mean_scores={"scoping_accuracy": 0.90},
        task_mean_scores={
            "retail.alpha.v1": 0.91,
            "retail.beta.v1": 0.92,
        },
    )

    snapshot = BuildRegressionBoard(
        _MemoryEvalStore(records),
        baseline_store=_MemoryBaselineStore(baseline),
    ).execute(recent_window=3, baseline_window_days=14)

    assert snapshot.baseline_source == "frozen"
    assert snapshot.frozen_baseline == baseline
    assert snapshot.overall.baseline.avg_weighted_score == 0.92
    kinds = {alert.kind for alert in snapshot.alerts}
    assert "pass_rate_drop" in kinds
    assert "dimension_regression" in kinds
    assert "single_task_hard_fail" in kinds
    assert "online_mode_drift" in kinds
    task_alert = next(
        alert for alert in snapshot.alerts if alert.kind == "single_task_hard_fail"
    )
    assert task_alert.scope_key == "retail.alpha.v1"


def test_freeze_regression_baseline_persists_recent_window_summary() -> None:
    now = 1_700_864_000.0
    records = [
        _record(
            task_id="retail.alpha.v1",
            run_id="run-old",
            recorded_at=now - 20 * 86_400,
            weighted_score=0.99,
            passed=True,
            scoping=0.98,
        ),
        _record(
            task_id="retail.alpha.v1",
            run_id="run-1",
            recorded_at=now - 6 * 86_400,
            weighted_score=0.90,
            passed=True,
            scoping=0.92,
        ),
        _record(
            task_id="retail.beta.v1",
            run_id="run-2",
            recorded_at=now - 4 * 86_400,
            weighted_score=0.80,
            passed=True,
            scoping=0.82,
        ),
        _record(
            task_id="retail.alpha.v1",
            run_id="run-3",
            recorded_at=now - 2 * 86_400,
            weighted_score=0.60,
            passed=False,
            scoping=0.62,
        ),
        _record(
            task_id="retail.beta.v1",
            run_id="run-4",
            recorded_at=now - 1 * 86_400,
            weighted_score=0.70,
            passed=True,
            scoping=0.72,
        ),
    ]
    baseline_store = _MemoryBaselineStore()

    baseline = FreezeRegressionBaseline(
        eval_store=_MemoryEvalStore(records),
        baseline_store=baseline_store,
    ).execute(
        commit_sha="freeze-commit",
        baseline_window_days=14,
    )

    assert baseline.commit_sha == "freeze-commit"
    assert baseline.source_point_count == 4
    assert baseline.pass_rate == 0.75
    assert baseline.weighted_score_mean == 0.75
    assert baseline.dimension_mean_scores["scoping_accuracy"] == 0.77
    assert baseline.task_mean_scores["retail.alpha.v1"] == 0.75
    assert baseline_store.load_latest() == baseline
