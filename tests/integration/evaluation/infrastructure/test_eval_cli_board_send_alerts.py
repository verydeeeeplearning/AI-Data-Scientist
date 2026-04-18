from __future__ import annotations

from pathlib import Path

from rich.console import Console

from ds_agent.evaluation.domain.entities.eval_score import EvalDatasetRecord, EvalScore
from ds_agent.evaluation.domain.entities.regression_alert_delivery import (
    RegressionAlertDelivery,
)
from ds_agent.evaluation.domain.entities.regression_board import (
    RegressionAlert,
    RegressionBoardSnapshot,
)
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.evaluation.infrastructure.cli import eval_cli
from ds_agent.evaluation.infrastructure.cli.eval_cli import run_eval_command
from ds_agent.evaluation.infrastructure.persistence.jsonl_eval_dataset_store import (
    JsonlEvalDatasetStore,
)


def test_eval_cli_board_send_alerts_dispatches_configured_channels(
    tmp_path: Path, monkeypatch
) -> None:
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
            weighted_score=0.42,
            passed=False,
            scores={
                "scoping_accuracy": EvalScore(
                    name="scoping_accuracy",
                    value=0.42,
                    rationale="fixture",
                    judge_type=JudgeType.DETERMINISTIC,
                )
            },
            run_metadata={"taskDomain": "retail"},
        )
    )

    class _FakeNotifier:
        def __init__(self, channel: str) -> None:
            self.channel = channel
            self.calls: list[tuple[RegressionAlert, ...]] = []

        def notify(
            self,
            *,
            snapshot: RegressionBoardSnapshot,
            alerts: tuple[RegressionAlert, ...],
        ) -> RegressionAlertDelivery:
            self.calls.append(alerts)
            return RegressionAlertDelivery(
                channel=self.channel,
                alert_count=len(alerts),
                target=f"{self.channel}-target",
                summary="sent",
            )

    slack = _FakeNotifier("slack")
    teams = _FakeNotifier("teams")
    monkeypatch.setattr(
        eval_cli,
        "build_configured_regression_alert_notifiers",
        lambda: (slack, teams),
    )

    console = Console(record=True, width=120)
    exit_code = run_eval_command(
        [
            "board",
            "send-alerts",
            "--dataset",
            str(dataset_path),
            "--tasks-dir",
            str(tasks_dir),
            "--channel",
            "slack",
            "--output",
            "json",
        ],
        console=console,
        workspace_dir=str(tmp_path),
    )

    output = console.export_text()
    assert exit_code == 0
    assert len(slack.calls) == 1
    assert len(teams.calls) == 0
    assert '"channel": "slack"' in output
    assert '"deliveries": [' in output
