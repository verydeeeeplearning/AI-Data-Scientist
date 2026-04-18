from __future__ import annotations

from pathlib import Path

from ds_agent.evaluation.infrastructure.gold_tasks.loader import GoldTaskLoader


def test_gold_task_loader_reads_bundled_suite() -> None:
    tasks_dir = (
        Path(__file__).resolve().parents[4]
        / "src"
        / "ds_agent"
        / "evaluation"
        / "infrastructure"
        / "gold_tasks"
        / "tasks"
    )

    tasks = GoldTaskLoader().load_suite(tasks_dir)

    assert len(tasks) >= 6
    ids = {task.id for task in tasks}
    assert "retail.churn_scoping.v1" in ids
    assert "finance.fraud_triage.v1" in ids
    assert "saas.trial_conversion_scoping.v1" in ids
    assert "ops.inventory_restock_risk.v1" in ids
    assert "healthcare.readmission_triage.v1" in ids
    assert "marketing.lead_scoring_pipeline.v1" in ids
