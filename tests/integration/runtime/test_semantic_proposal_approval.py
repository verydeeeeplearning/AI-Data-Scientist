from __future__ import annotations

from ds_agent.domain.entities.approval import ApprovalStatus
from ds_agent.infrastructure.semantic_memory_container import build_semantic_memory_container
from ds_agent.infrastructure.semantic_memory_runtime import resolve_semantic_db_path
from ds_agent.memory.semantic.domain.proposal import (
    SemanticProposalStatus,
    SemanticProposalType,
)
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.semantic_proposal_router import (
    create_semantic_proposal_approval,
    resolve_semantic_proposal_approval,
)


def test_semantic_proposal_approval_apply_round_trip(tmp_path) -> None:
    db_path = resolve_semantic_db_path(tmp_path)
    container = build_semantic_memory_container(
        workspace_dir=str(tmp_path),
        db_path=str(db_path),
    )
    submission = container.submit_semantic_proposal.execute(
        proposal_type=SemanticProposalType.VERIFIED_QUERY,
        summary="Verified query candidate for monthly_churn_rate",
        payload={
            "vq_id": "vq-monthly-churn-postgres",
            "metric_id": "monthly_churn_rate",
            "dialect": "postgres",
            "description": "Verified monthly churn query",
            "sql_template": "SELECT 0.05 AS monthly_churn_rate",
            "referenced_tables": ["prod.growth.subscription"],
            "verified_by": "reviewer@corp.example",
            "last_verified": "2026-04-16",
            "verification_evidence": "Dashboard parity with Growth board",
        },
        target_id="monthly_churn_rate",
        evidence_refs=["verdict:RV-1"],
        confidence=0.91,
        risk="high",
        source_run_id="TC-1:session-1",
        source_session_id="session-1",
        source_tool_name="run_verifier",
    )

    store = JsonApprovalStore(base_dir=tmp_path)
    approval = create_semantic_proposal_approval(
        approval_store=store,
        proposal=submission.proposal,
        session_id="session-1",
        run_id="TC-1:session-1",
        surface="agent",
    )
    resolved = store.resolve(
        approval.approval_id,
        status=ApprovalStatus.APPROVED,
        response="apply",
        source="ws",
        actor="operator@corp.example",
    )

    assert resolved is not None
    outcome = resolve_semantic_proposal_approval(
        resolved,
        workspace_dir=str(tmp_path),
        reviewer="operator@corp.example",
    )
    persisted = container.proposals.get(submission.proposal.proposal_id)
    query = container.verified_queries.get("vq-monthly-churn-postgres")

    assert outcome.applied is True
    assert outcome.action == "apply"
    assert outcome.applied_target == "vq-monthly-churn-postgres"
    assert persisted is not None
    assert persisted.status is SemanticProposalStatus.APPLIED
    assert query is not None
