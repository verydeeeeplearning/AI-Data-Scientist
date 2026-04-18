from __future__ import annotations

from rich.console import Console

from ds_agent.evaluation.domain.entities.eval_score import EvalDatasetRecord, EvalScore
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.evaluation.infrastructure.cli.eval_cli import run_eval_command
from ds_agent.evaluation.infrastructure.persistence.jsonl_eval_dataset_store import (
    JsonlEvalDatasetStore,
)


def _record(
    *,
    task_id: str,
    run_id: str,
    recorded_at: float,
    weighted_score: float,
    passed: bool,
    scoping: float,
) -> EvalDatasetRecord:
    return EvalDatasetRecord(
        recorded_at=recorded_at,
        task_id=task_id,
        run_id=run_id,
        mode="offline",
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


def test_eval_cli_board_freezes_baseline_and_builds_snapshot(tmp_path) -> None:
    dataset_path = tmp_path / "dataset_records.jsonl"
    baseline_path = tmp_path / "regression_baseline.json"
    store = JsonlEvalDatasetStore(dataset_path)
    for record in (
        _record(
            task_id="retail.alpha.v1",
            run_id="run-1",
            recorded_at=1_700_000_000.0,
            weighted_score=0.96,
            passed=True,
            scoping=0.94,
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
            weighted_score=0.58,
            passed=False,
            scoping=0.60,
        ),
        _record(
            task_id="retail.beta.v1",
            run_id="run-4",
            recorded_at=1_700_086_410.0,
            weighted_score=0.76,
            passed=True,
            scoping=0.62,
        ),
    ):
        store.append(record)

    freeze_console = Console(record=True, width=140)
    freeze_exit = run_eval_command(
        [
            "board",
            "freeze-baseline",
            "--dataset",
            str(dataset_path),
            "--baseline",
            str(baseline_path),
            "--commit",
            "commit-freeze",
            "--output",
            "json",
        ],
        console=freeze_console,
        workspace_dir=str(tmp_path),
    )

    assert freeze_exit == 0
    assert '"commit_sha": "commit-freeze"' in freeze_console.export_text()

    snapshot_console = Console(record=True, width=140)
    snapshot_exit = run_eval_command(
        [
            "board",
            "snapshot",
            "--dataset",
            str(dataset_path),
            "--baseline",
            str(baseline_path),
            "--output",
            "json",
        ],
        console=snapshot_console,
        workspace_dir=str(tmp_path),
    )

    output = snapshot_console.export_text()
    assert snapshot_exit == 0
    assert '"baseline_source": "frozen"' in output
    assert '"frozen_baseline": {' in output
    assert '"kind": "pass_rate_drop"' in output
    assert '"kind": "dimension_regression"' in output
