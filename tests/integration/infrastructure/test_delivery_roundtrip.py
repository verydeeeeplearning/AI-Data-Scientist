from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from ds_agent.application.dtos.task_contract import (
    BuildDeliveryPackDTO,
    DispatchDeliveryDTO,
    ListDeliveryLogDTO,
    RenderDeliveryArtifactDTO,
    TaskContractDraftDTO,
)
from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore
from ds_agent.infrastructure.task_contract_container import build_task_contract_container


def _workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / f"delivery-roundtrip-{uuid.uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_delivery_roundtrip_persists_sqlite_dispatch_log(tmp_path: Path) -> None:
    workspace_root = _workspace_root(tmp_path)
    db_path = workspace_root / "task_contracts.db"
    store = SqliteTaskContractStore(db_path)
    container = build_task_contract_container(str(workspace_root), store=store)

    created = container.create.execute(
        TaskContractDraftDTO(
            session_id="session-1",
            contract_type="churn_analysis",
            business_goal="Reduce churn",
            goal_brief={
                "business_question": "Why is churn increasing?",
                "ds_problem_statement": "Prioritize interventions",
                "comparison_baseline": "Current playbook",
                "decision_to_make": "Approve retention sprint",
                "expected_effort": "M",
            },
            required_deliverables=[
                {"type": "pm_action_memo", "audience": "pm", "format": "markdown"}
            ],
        )
    )
    built = container.build_delivery_pack.execute(
        BuildDeliveryPackDTO(
            task_id=created["task_id"],
            source_analysis_id="FA-42",
            global_context={"project": "churn-retention"},
        )
    )
    artifact_id = built["artifact_ids"][0]
    rendered = container.render_delivery_artifact.execute(
        RenderDeliveryArtifactDTO(
            task_id=created["task_id"],
            artifact_id=artifact_id,
            analysis={
                "summary": "Premium cohorts drove the churn spike.",
                "next_actions": ["Create retention experiment", "Assign PM owner"],
                "eta": "2 weeks",
                "trade_offs": [
                    {"option": "discount", "benefit": "fast lift", "risk": "margin erosion"}
                ],
                "dependencies": ["pricing review"],
            },
            output_dir=str(workspace_root / "artifacts"),
        )
    )
    dispatched = container.dispatch_delivery.execute(
        DispatchDeliveryDTO(
            task_id=created["task_id"],
            artifact_ids=[artifact_id],
            approve_manual_review=True,
        )
    )
    delivery_log = container.list_delivery_log.execute(
        ListDeliveryLogDTO(
            task_id=created["task_id"],
            pack_id=built["pack_id"],
            artifact_ids=[artifact_id],
            limit=10,
        )
    )

    assert rendered["pack_status"] == "rendered"
    assert dispatched["dispatch_status"] == "dispatched"
    assert dispatched["sent"] == 2
    assert delivery_log["returned"] == 2
    assert delivery_log["summary"]["pack_status"] == "dispatched"
    assert delivery_log["summary"]["artifact_count"] == 1
    assert delivery_log["summary"]["rendered_count"] == 1
    assert delivery_log["summary"]["sent"] == 2

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        logs = conn.execute(
            """
            SELECT status, channel, receipt_ref, adapter_name
            FROM delivery_log
            WHERE pack_id = ?
            ORDER BY log_id
            """,
            (built["pack_id"],),
        ).fetchall()
        summary = conn.execute(
            """
            SELECT status, artifact_count, rendered_count, last_attempt
            FROM v_delivery_summary
            WHERE pack_id = ?
            """,
            (built["pack_id"],),
        ).fetchone()

    assert len(logs) == 2
    assert {row["channel"] for row in logs} == {"slack_channel", "notion_page"}
    assert {row["status"] for row in logs} == {"sent"}
    assert all(row["receipt_ref"] for row in logs)
    assert all(row["adapter_name"] for row in logs)
    assert summary is not None
    assert summary["status"] == "dispatched"
    assert summary["artifact_count"] == 1
    assert summary["rendered_count"] == 1
    assert summary["last_attempt"] is not None
