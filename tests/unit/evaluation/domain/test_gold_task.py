from __future__ import annotations

import pytest
from pydantic import ValidationError

from ds_agent.evaluation.domain.entities.gold_task import GoldTask


def _task_payload() -> dict[str, object]:
    return {
        "id": "retail.churn_scoping.v1",
        "task_version": 1,
        "domain": "retail",
        "difficulty": "medium",
        "prompt": "Score a churn triage run.",
        "input": {
            "datasets": [{"name": "subscriptions", "source": "fixtures/subscriptions.parquet"}],
            "snapshot_date": "2024-12-31",
            "budget_usd": 20.0,
            "time_budget_min": 30,
        },
        "expected_deliverables": [
            {
                "type": "goal_brief",
                "must_contain": [
                    "problem_framing",
                    "kpi_definition",
                    "segment_definition",
                ],
            },
            {"type": "executive_summary"},
        ],
        "validation_points": {
            "metric_selection": {
                "acceptable_primary": ["pr_auc", "lift_at_10pct"],
                "forbidden_primary": ["accuracy"],
            },
            "approval_required": {"sending_campaign": True},
        },
        "scoring_rubric": {
            "scoping_accuracy": {"weight": 0.15, "judge": "llm"},
            "metric_selection_accuracy": {"weight": 0.10, "judge": "hybrid"},
            "temporal_leakage_detection": {"weight": 0.15, "judge": "deterministic"},
            "tool_trajectory": {"weight": 0.05, "judge": "deterministic"},
            "artifact_faithfulness": {"weight": 0.15, "judge": "llm"},
            "exec_summary_accuracy": {"weight": 0.10, "judge": "llm"},
            "approval_judgment": {"weight": 0.10, "judge": "hybrid"},
            "session_completeness": {"weight": 0.10, "judge": "hybrid"},
            "operator_satisfaction": {"weight": 0.05, "judge": "human_or_proxy"},
            "time_to_decision": {"weight": 0.05, "judge": "deterministic"},
        },
        "pass_threshold": 0.75,
        "alert_on_drop_below": 0.70,
    }


def test_gold_task_accepts_valid_payload() -> None:
    task = GoldTask.model_validate(_task_payload())

    assert task.id == "retail.churn_scoping.v1"
    assert len(task.scoring_rubric) == 10


def test_gold_task_rejects_weight_sum_not_equal_to_one() -> None:
    payload = _task_payload()
    scoring_rubric = dict(payload["scoring_rubric"])
    scoring_rubric["time_to_decision"] = {"weight": 0.15, "judge": "deterministic"}
    payload["scoring_rubric"] = scoring_rubric

    with pytest.raises(ValidationError):
        GoldTask.model_validate(payload)


def test_gold_task_rejects_pass_threshold_below_alert() -> None:
    payload = _task_payload()
    payload["pass_threshold"] = 0.60

    with pytest.raises(ValidationError):
        GoldTask.model_validate(payload)

