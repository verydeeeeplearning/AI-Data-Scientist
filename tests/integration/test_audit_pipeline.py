from __future__ import annotations

from pathlib import Path

from ds_agent.application.dtos.task_contract import (
    BuildDeliveryPackDTO,
    DispatchDeliveryDTO,
    ListDeliveryLogDTO,
    RenderDeliveryArtifactDTO,
    TaskContractDraftDTO,
)
from ds_agent.infrastructure.task_contract_container import build_task_contract_container


def test_audit_pipeline_renders_pdf_and_dispatches_to_compliance(tmp_path: Path) -> None:
    workspace_dir = str(tmp_path / "workspace")
    container = build_task_contract_container(workspace_dir)
    created = container.create.execute(
        TaskContractDraftDTO(
            session_id="session-audit",
            contract_type="churn_analysis",
            business_goal="Produce a regulated audit trail",
            goal_brief={
                "business_question": "Was the model released under policy?",
                "ds_problem_statement": "Assemble audit evidence",
                "comparison_baseline": "Current release record",
                "decision_to_make": "Approve regulator submission",
                "expected_effort": "M",
            },
            required_deliverables=[
                {"type": "audit_trail", "audience": "auditor", "format": "pdf"}
            ],
        )
    )
    built = container.build_delivery_pack.execute(
        BuildDeliveryPackDTO(
            task_id=created["task_id"],
            audiences=["auditor"],
            source_analysis_id="AUD-42",
            signed_by="auditor@test",
            signature="signed-blob",
        )
    )
    artifact_id = built["artifact_ids"][0]

    rendered = container.render_delivery_artifact.execute(
        RenderDeliveryArtifactDTO(
            task_id=created["task_id"],
            artifact_id=artifact_id,
            analysis={
                "summary": "Release evidence collected.",
                "data_provenance": "warehouse.curated_churn",
                "policy_compliance": "retention and access checks passed",
                "approval_chain": ["qa_signoff", "risk_review"],
                "lineage": ["lineage-1", "lineage-2"],
            },
            output_dir=str(tmp_path / "artifacts"),
        )
    )
    dispatched = container.dispatch_delivery.execute(
        DispatchDeliveryDTO(task_id=created["task_id"])
    )
    delivery_log = container.list_delivery_log.execute(
        ListDeliveryLogDTO(task_id=created["task_id"], pack_id=built["pack_id"], limit=10)
    )

    assert rendered["format"] == "pdf"
    assert Path(rendered["output_path"]).read_bytes().startswith(b"%PDF")
    assert dispatched["dispatch_status"] == "dispatched"
    assert dispatched["sent"] == 1
    assert delivery_log["summary"]["pack_status"] == "dispatched"
    assert delivery_log["summary"]["sent"] == 1
    assert delivery_log["records"][0]["channel"] == "compliance_system"
