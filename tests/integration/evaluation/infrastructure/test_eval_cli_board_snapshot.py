from __future__ import annotations

from pathlib import Path

from rich.console import Console

from ds_agent.evaluation.domain.entities.eval_score import EvalDatasetRecord, EvalScore
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.evaluation.infrastructure.cli.eval_cli import run_eval_command
from ds_agent.evaluation.infrastructure.persistence.jsonl_eval_dataset_store import (
    JsonlEvalDatasetStore,
)


def test_eval_cli_board_snapshot_renders_json_payload(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.jsonl"
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "retail.margin_watch.v1.yaml").write_text(
        """
id: retail.margin_watch.v1
task_version: 1
domain: retail
difficulty: medium
prompt: Review margin drift.
input:
  datasets: []
scoring_rubric:
  scoping_accuracy:
    weight: 1.0
    judge: deterministic
pass_threshold: 0.60
alert_on_drop_below: 0.50
""".strip(),
        encoding="utf-8",
    )
    store = JsonlEvalDatasetStore(dataset_path)
    store.append(
        EvalDatasetRecord(
            recorded_at=1_700_000_000.0,
            task_id="retail.margin_watch.v1",
            run_id="run-1",
            mode="offline",
            weighted_score=0.83,
            passed=True,
            scores={
                "scoping_accuracy": EvalScore(
                    name="scoping_accuracy",
                    value=0.83,
                    rationale="fixture",
                    judge_type=JudgeType.DETERMINISTIC,
                )
            },
        )
    )

    console = Console(record=True, width=120)
    exit_code = run_eval_command(
        [
            "board",
            "snapshot",
            "--dataset",
            str(dataset_path),
            "--tasks-dir",
            str(tasks_dir),
            "--output",
            "json",
        ],
        console=console,
        workspace_dir=str(tmp_path),
    )

    output = console.export_text()
    assert exit_code == 0
    assert '"total_records": 1' in output
    assert '"available_domains": [' in output
    assert '"task_id": "retail.margin_watch.v1"' in output
