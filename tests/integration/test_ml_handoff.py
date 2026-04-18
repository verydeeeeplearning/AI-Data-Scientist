from __future__ import annotations

from ds_agent.application.dtos.task_contract import (
    BuildDeliveryPackDTO,
    DispatchDeliveryDTO,
    ListDeliveryLogDTO,
    RenderDeliveryArtifactDTO,
    TaskContractDraftDTO,
)
from ds_agent.infrastructure.task_contract_container import build_task_contract_container


def test_ml_handoff_pipeline_dispatches_to_confluence_and_jira(tmp_path) -> None:
    workspace_dir = str(tmp_path / "workspace")
    container = build_task_contract_container(workspace_dir)
    created = container.create.execute(
        TaskContractDraftDTO(
            session_id="session-ml",
            contract_type="churn_analysis",
            business_goal="Hand the model off to ML engineering",
            goal_brief={
                "business_question": "How should the model be productionized?",
                "ds_problem_statement": "Document serving and rollback requirements",
                "comparison_baseline": "Current deployment runbook",
                "decision_to_make": "Approve production handoff",
                "expected_effort": "M",
            },
            required_deliverables=[
                {"type": "ml_handoff_spec", "audience": "ml_engineer", "format": "markdown"}
            ],
        )
    )
    built = container.build_delivery_pack.execute(
        BuildDeliveryPackDTO(task_id=created["task_id"], audiences=["ml_engineer"])
    )
    artifact_id = built["artifact_ids"][0]

    rendered = container.render_delivery_artifact.execute(
        RenderDeliveryArtifactDTO(
            task_id=created["task_id"],
            artifact_id=artifact_id,
            analysis={
                "summary": "Production handoff ready.",
                "serving_config": {"image": "model:2026.04", "cpu": "2", "memory": "4Gi"},
                "monitoring_setup": ["latency_p95", "prediction_drift"],
                "rollback_plan": "restore previous blessed model",
            },
            output_dir=str(tmp_path / "artifacts"),
        )
    )
    dispatched = container.dispatch_delivery.execute(
        DispatchDeliveryDTO(
            task_id=created["task_id"],
            approve_manual_review=True,
        )
    )
    delivery_log = container.list_delivery_log.execute(
        ListDeliveryLogDTO(task_id=created["task_id"], pack_id=built["pack_id"], limit=10)
    )

    assert rendered["format"] == "markdown"
    assert dispatched["dispatch_status"] == "dispatched"
    assert dispatched["sent"] == 2
    assert {entry["channel"] for entry in delivery_log["records"]} == {
        "confluence",
        "jira_ticket",
    }
