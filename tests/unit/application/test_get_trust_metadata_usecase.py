from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ds_agent.application.use_cases.get_trust_metadata_usecase import (
    GetTrustMetadataUseCase,
)
from ds_agent.domain.entities.approval import ApprovalStatus
from ds_agent.domain.entities.certification import CertificationRecord
from ds_agent.domain.entities.lineage import LineageRecord, LineageRecordType
from ds_agent.domain.entities.post_deploy import PostDeployMonitorState
from ds_agent.domain.entities.review_verdict import CheckResult, LayerResult, ReviewVerdict
from ds_agent.infrastructure.persistence.certification_store import SqliteCertificationStore
from ds_agent.infrastructure.persistence.deploy_monitor_state_store import (
    SqliteDeployMonitorStateStore,
)
from ds_agent.infrastructure.persistence.lineage_store import SqliteLineageStore
from ds_agent.infrastructure.persistence.verdict_repo import SqliteVerdictRepository
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.runtime_event_log import RuntimeEventLog


def _seed_trust_workspace(
    workspace_dir: str,
    result_id: str,
    *,
    lineage_record_id: str | None = None,
    approval_session_id: str | None = None,
    approval_run_id: str | None = None,
    event_session_id: str | None = None,
    event_run_id: str | None = None,
    fallback_message: str = "Provider fallback used",
    sandbox_message: str = "Sandbox blocked subprocess",
    fallback_metadata: dict[str, object] | None = None,
    sandbox_metadata: dict[str, object] | None = None,
) -> dict[str, str]:
    verdict_store = SqliteVerdictRepository.for_workspace(workspace_dir)
    verdict_store.save(
        ReviewVerdict(
            verdict_id="RV-10001",
            task_id=result_id,
            category="orchestrator",
            reviewer="verifier_orchestrator",
            created_at=datetime(2026, 4, 19, 8, 30, tzinfo=UTC),
            layers=[
                LayerResult(
                    layer="statistical",
                    overall="pass",
                    checks=[
                        CheckResult(
                            check_id="stat-1",
                            status="pass",
                            score=1.0,
                            evidence={},
                            message="statistical checks passed",
                        )
                    ],
                ),
                LayerResult(
                    layer="policy",
                    overall="warn",
                    checks=[
                        CheckResult(
                            check_id="policy-1",
                            status="warn",
                            score=0.6,
                            evidence={},
                            message="policy needs review",
                        )
                    ],
                ),
            ],
            metadata={"primary_model": "anthropic/claude-sonnet-4-6"},
        )
    )

    lineage_store = SqliteLineageStore(
        str(Path(workspace_dir) / "data" / "memory" / "lineage.db")
    )
    root = LineageRecord(
        id="lineage-root",
        record_type=LineageRecordType.DATASET,
        content={"source": "train.csv"},
        session_id=result_id,
        timestamp=1_745_056_200.0,
    )
    child = LineageRecord(
        id=lineage_record_id or result_id,
        record_type=LineageRecordType.MODEL,
        parent_id=root.id,
        content={"model": "model-a"},
        session_id=result_id,
        timestamp=1_745_059_800.0,
    )
    lineage_store.save(root)
    lineage_store.save(child)

    cert_store = SqliteCertificationStore.for_workspace(workspace_dir)
    cert_store.save_certification(
        CertificationRecord(
            mission_name=result_id,
            mission_version=1,
            level="autopilot",
            transition_from="delegate",
            approved_by=("owner-cho",),
            approved_at=datetime(2026, 4, 19, 10, 0, tzinfo=UTC),
            evidence_ref="RV-10001",
            next_review=None,
        )
    )

    approval_store = JsonApprovalStore(workspace_dir)
    approval = approval_store.create(
        session_id=approval_session_id or result_id,
        run_id=approval_run_id or result_id,
        surface="electron",
        question="Approve trust projection?",
        kind="trust_projection",
        metadata={"resultId": result_id},
        options=["approve", "reject"],
        default="approve",
    )
    approval.status = ApprovalStatus.APPROVED
    approval.response = "approve"
    approval.source = "owner-cho"
    approval.actor = "owner-cho"
    approval.resolved_at = 1_745_063_400.0
    approval.updated_at = 1_745_063_400.0
    approval_store.replace(approval)

    event_log = RuntimeEventLog(workspace_dir)
    fallback_event = event_log.record(
        category="health",
        kind="provider.fallback",
        severity="info",
        message=fallback_message,
        session_id=event_session_id or result_id,
        run_id=event_run_id or result_id,
        metadata={
            "from": "anthropic/claude-sonnet-4-6",
            "to": "openai/gpt-4.1",
            "resultId": result_id,
            **(fallback_metadata or {}),
        },
        created_at=1_745_063_100.0,
    )
    sandbox_event = event_log.record(
        category="runtime",
        kind="sandbox.violation",
        severity="warning",
        message=sandbox_message,
        session_id=event_session_id or result_id,
        run_id=event_run_id or result_id,
        metadata={"tool": "code_execution", "resultId": result_id, **(sandbox_metadata or {})},
        created_at=1_745_063_200.0,
    )

    drift_store = SqliteDeployMonitorStateStore.for_workspace(workspace_dir)
    drift_store.save(
        PostDeployMonitorState.model_validate(
            {
                "state_id": "deploy-1",
                "model_id": result_id,
                "model_version": 1,
                "alias": "champion",
                "window": "24h",
                "observed_at": datetime(2026, 4, 19, 10, 30, tzinfo=UTC),
                "drift": {
                    "overall_status": "warning",
                    "max_psi": 0.31,
                    "max_ks": 0.18,
                    "top_drifting_features": ["feature_a"],
                    "metrics": [],
                },
                "metrics": [],
                "service_level": {
                    "latency_p95_ms": 120.0,
                    "latency_budget_ms": 100,
                    "qps": 25.0,
                    "throughput_budget_qps": 30,
                    "status": "warning",
                },
                "remediation": {
                    "decision": "rollback",
                    "severity": "high",
                    "rationale": "PSI exceeded threshold.",
                    "should_alert": True,
                    "recommended_steps": ["rollback"],
                },
                "overall_status": "alert",
                "alerts": ["drift alert"],
                "trigger_mode": "auto_rollback",
                "trigger_payload": {"executed": False},
            }
        )
    )

    return {
        "fallback_event_id": fallback_event.event_id,
        "sandbox_event_id": sandbox_event.event_id,
    }


def _use_case_for_workspace(workspace_dir: str) -> GetTrustMetadataUseCase:
    return GetTrustMetadataUseCase(
        verdict_repo=SqliteVerdictRepository.for_workspace(workspace_dir),
        lineage_store=SqliteLineageStore(
            str(Path(workspace_dir) / "data" / "memory" / "lineage.db")
        ),
        certification_store=SqliteCertificationStore.for_workspace(workspace_dir),
        approval_store=JsonApprovalStore(workspace_dir),
        drift_store=SqliteDeployMonitorStateStore.for_workspace(workspace_dir),
        event_log=RuntimeEventLog(workspace_dir),
    )


def test_get_trust_metadata_use_case_projects_real_store_data(tmp_path) -> None:
    workspace = str(tmp_path / "workspace")
    result_id = "result-001"
    evidence = _seed_trust_workspace(workspace, result_id)

    use_case = _use_case_for_workspace(workspace)
    trust = use_case.execute(result_id)

    assert trust.result_id == result_id
    assert trust.verifier.status == "yellow"
    assert trust.verifier.passed == 1
    assert trust.lineage.status == "captured"
    assert trust.lineage.ancestor_count == 1
    assert trust.fallback.occurred is True
    assert trust.fallback.fallback_id == evidence["fallback_event_id"]
    assert trust.fallback.event_count == 1
    assert trust.fallback.status == "warning"
    assert trust.fallback.summary == "anthropic/claude-sonnet-4-6 -> openai/gpt-4.1"
    assert trust.approval.required is True
    assert trust.approval.approved_by == "owner-cho"
    assert trust.drift.status == "yellow"
    assert trust.drift.psi == pytest.approx(0.31)
    assert trust.sandbox.violation_occurred is True
    assert trust.sandbox.event_id == evidence["sandbox_event_id"]
    assert trust.sandbox.event_count == 1
    assert trust.sandbox.summary == "code_execution: Sandbox blocked subprocess"
    assert trust.certification is not None
    assert trust.certification.level == "platinum"
    assert trust.model.primary == "anthropic/claude-sonnet-4-6"
    assert trust.confidence.level == "medium"
    assert trust.data_window is not None
    assert trust.data_window.days >= 1


def test_get_trust_metadata_uses_explicit_result_id_before_legacy_ids(tmp_path) -> None:
    workspace = str(tmp_path / "workspace")
    result_id = "result-explicit-001"
    evidence = _seed_trust_workspace(
        workspace,
        result_id,
        lineage_record_id="lineage-model-001",
        approval_session_id="session-approval-001",
        approval_run_id="run-approval-001",
        event_session_id="session-event-001",
        event_run_id="run-event-001",
    )
    event_log = RuntimeEventLog(workspace)
    event_log.record(
        category="health",
        kind="provider.fallback",
        severity="info",
        message="Legacy fallback should not win",
        session_id=result_id,
        run_id=result_id,
        metadata={"from": "legacy/model-a", "to": "legacy/model-b"},
        created_at=1_745_063_150.0,
    )
    event_log.record(
        category="runtime",
        kind="sandbox.violation",
        severity="warning",
        message="Legacy sandbox should not win",
        session_id=result_id,
        run_id=result_id,
        metadata={"tool": "legacy_tool"},
        created_at=1_745_063_250.0,
    )

    use_case = _use_case_for_workspace(workspace)
    trust = use_case.execute(result_id)

    assert trust.result_id == result_id
    assert trust.approval.approval_id is not None
    assert trust.approval.approval_status == ApprovalStatus.APPROVED.value
    assert trust.approval.approved_by == "owner-cho"
    assert trust.fallback.occurred is True
    assert trust.fallback.fallback_id == evidence["fallback_event_id"]
    assert trust.fallback.event_count == 1
    assert trust.fallback.summary == "anthropic/claude-sonnet-4-6 -> openai/gpt-4.1"
    assert trust.sandbox.violation_occurred is True
    assert trust.sandbox.event_id == evidence["sandbox_event_id"]
    assert trust.sandbox.event_count == 1
    assert trust.sandbox.summary == "code_execution: Sandbox blocked subprocess"


def test_get_trust_metadata_bounds_runtime_event_summaries(tmp_path) -> None:
    workspace = str(tmp_path / "workspace")
    result_id = "result-events-001"
    long_text = "x" * 240
    event_log = RuntimeEventLog(workspace)
    fallback_event = event_log.record(
        category="health",
        kind="provider.fallback",
        severity="info",
        message=long_text,
        metadata={"resultId": result_id},
        created_at=1_745_063_100.0,
    )
    sandbox_event = event_log.record(
        category="runtime",
        kind="sandbox.violation",
        severity="warning",
        message="Sandbox violation observed",
        metadata={
            "resultId": result_id,
            "tool": "code_execution",
            "detail": long_text,
        },
        created_at=1_745_063_200.0,
    )

    trust = _use_case_for_workspace(workspace).execute(result_id)

    assert trust.fallback.fallback_id == fallback_event.event_id
    assert trust.fallback.event_count == 1
    assert trust.fallback.summary is not None
    assert len(trust.fallback.summary) <= 160
    assert trust.fallback.summary.endswith("...")
    assert trust.sandbox.event_id == sandbox_event.event_id
    assert trust.sandbox.event_count == 1
    assert trust.sandbox.summary is not None
    assert len(trust.sandbox.summary) <= 160
    assert trust.sandbox.summary.endswith("...")


def test_get_trust_metadata_use_case_raises_for_unknown_result(tmp_path) -> None:
    workspace = str(tmp_path / "workspace")
    use_case = _use_case_for_workspace(workspace)

    with pytest.raises(ValueError, match="Trust metadata not found"):
        use_case.execute("missing-result")
