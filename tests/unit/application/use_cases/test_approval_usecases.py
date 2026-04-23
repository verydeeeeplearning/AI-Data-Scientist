from __future__ import annotations

from dataclasses import dataclass

import pytest

from ds_agent.application.use_cases.get_approval_request_usecase import (
    ApprovalRequestView,
    GetApprovalRequestUseCase,
)
from ds_agent.application.use_cases.submit_approval_usecase import (
    SubmitApprovalRequest,
    SubmitApprovalUseCase,
)
from ds_agent.domain.entities.approval import ApprovalRequest, ApprovalStatus
from ds_agent.domain.security.risk_pattern_descriptions import PATTERN_DESCRIPTIONS
from ds_agent.runtime.approval_store import JsonApprovalStore


def test_risk_pattern_catalog_includes_30_plus_entries() -> None:
    assert len(PATTERN_DESCRIPTIONS) >= 30
    assert PATTERN_DESCRIPTIONS["PAT_001_SUBPROCESS_NETWORK"]["severity"] == "high"
    assert "subprocess" in PATTERN_DESCRIPTIONS["PAT_001_SUBPROCESS_NETWORK"]["affected"]
    assert PATTERN_DESCRIPTIONS["PAT_002_FILE_WRITE_OUTSIDE_WORKSPACE"]["affected"] == [
        "filesystem"
    ]
    assert "secret" in PATTERN_DESCRIPTIONS["PAT_005_SECRET_ENV_ACCESS"]["affected"]


@dataclass
class _ApprovalStubStore:
    approval: ApprovalRequest

    def get(self, approval_id: str) -> ApprovalRequest | None:
        return self.approval if approval_id == self.approval.approval_id else None

    def resolve(
        self,
        approval_id: str,
        *,
        status: ApprovalStatus,
        response: str | None = None,
        source: str | None = None,
        actor: str | None = None,
    ) -> ApprovalRequest | None:
        if approval_id != self.approval.approval_id:
            return None
        self.approval.status = status
        self.approval.response = response
        self.approval.source = source
        self.approval.actor = actor
        return self.approval

    def replace(self, approval: ApprovalRequest) -> None:
        self.approval = approval


def test_get_approval_request_enriches_risk_metadata(tmp_path) -> None:
    store = JsonApprovalStore(base_dir=tmp_path)
    approval = store.create(
        session_id="session-1",
        run_id="run-1",
        surface="ws",
        question="Allow the export?",
        kind="PAT_002_FILE_WRITE_OUTSIDE_WORKSPACE",
        metadata={
            "workspaceId": "workspace-7",
            "triggeredBy": {"runId": "run-1", "toolCallId": "tool-9"},
            "riskCode": "PAT_002_FILE_WRITE_OUTSIDE_WORKSPACE",
            "expiresAt": 1234.5,
        },
        options=["allow", "deny"],
        default="deny",
    )

    result = GetApprovalRequestUseCase(store).execute(approval.approval_id)

    assert isinstance(result, ApprovalRequestView)
    assert result.risk_code == "PAT_002_FILE_WRITE_OUTSIDE_WORKSPACE"
    assert result.workspace_id == "workspace-7"
    assert result.triggered_by == {"runId": "run-1", "toolCallId": "tool-9"}
    assert result.expires_at == 1234.5
    assert result.pattern_matches[0].pattern_id == "PAT_002_FILE_WRITE_OUTSIDE_WORKSPACE"
    assert result.pattern_matches[0].description == "Write outside the workspace"
    assert result.affected_scopes == ["filesystem"]
    assert result.recommended_alternative == (
        "Write through a workspace-relative artifact path only."
    )


def test_get_approval_request_uses_explicit_pattern_matches() -> None:
    approval = ApprovalRequest(
        approval_id="approval-1",
        session_id="session-2",
        run_id="run-2",
        surface="agent",
        question="Approve this action?",
        kind="risk",
        metadata={
            "patternMatches": [
                {
                    "patternId": "PAT_008_HTTP_REQUEST_UNAPPROVED",
                    "highlightedLines": [
                        {"line": 4, "reason": "calls remote URL"},
                        [9, "retries the request"],
                    ],
                }
            ]
        },
    )
    result = GetApprovalRequestUseCase(_ApprovalStubStore(approval)).execute(approval)

    assert result.risk_code == "PAT_008_HTTP_REQUEST_UNAPPROVED"
    assert result.pattern_matches[0].highlighted_lines[0].line == 4
    assert result.pattern_matches[0].highlighted_lines[0].reason == "calls remote URL"
    assert result.pattern_matches[0].highlighted_lines[1].line == 9
    assert "network" in result.affected_scopes


def test_submit_approval_persists_scope_and_fallback_metadata(tmp_path) -> None:
    store = JsonApprovalStore(base_dir=tmp_path)
    approval = store.create(
        session_id="session-3",
        run_id="run-3",
        surface="ws",
        question="Approve network access?",
        metadata={"riskCode": "PAT_008_HTTP_REQUEST_UNAPPROVED"},
    )

    result = SubmitApprovalUseCase(store).execute(
        SubmitApprovalRequest(
            approval_id=approval.approval_id,
            decision="allow",
            scope="session",
            allow_fallback=True,
            actor="operator@example.com",
            source="ws",
        )
    )

    persisted = store.get(approval.approval_id)
    assert persisted is not None
    assert persisted.status == ApprovalStatus.APPROVED
    assert persisted.response is None
    assert persisted.metadata["approvalScope"] == "session"
    assert persisted.metadata["allowFallback"] is True
    assert persisted.metadata["approvalDecision"]["decision"] == "allow"
    assert result.scope == "session"
    assert result.allow_fallback is True
    assert result.response is None
    assert result.approval is not None


def test_submit_approval_rejects_with_reason_and_persists_metadata(tmp_path) -> None:
    store = JsonApprovalStore(base_dir=tmp_path)
    approval = store.create(
        session_id="session-4",
        run_id="run-4",
        surface="ws",
        question="Approve filesystem delete?",
    )

    result = SubmitApprovalUseCase(store).execute(
        {
            "approvalId": approval.approval_id,
            "decision": "deny",
            "denyReason": "Dangerous delete path",
            "allowFallback": False,
            "source": "ws",
        }
    )

    persisted = store.get(approval.approval_id)
    assert persisted is not None
    assert persisted.status == ApprovalStatus.REJECTED
    assert persisted.response == "Dangerous delete path"
    assert persisted.metadata["denyReason"] == "Dangerous delete path"
    assert persisted.metadata["approvalDecision"]["decision"] == "deny"
    assert result.denied_reason == "Dangerous delete path"
    assert result.response == "Dangerous delete path"


def test_submit_approval_accepts_request_id_alias_and_preserves_explicit_response(tmp_path) -> None:
    store = JsonApprovalStore(base_dir=tmp_path)
    approval = store.create(
        session_id="session-4b",
        run_id="run-4b",
        surface="ws",
        question="Apply this proposal?",
        kind="semantic_proposal",
    )

    result = SubmitApprovalUseCase(store).execute(
        {
            "requestId": approval.approval_id,
            "decision": "allow",
            "scope": "workspace",
            "response": "apply",
            "source": "ws",
            "actor": "reviewer@example.com",
        }
    )

    persisted = store.get(approval.approval_id)
    assert persisted is not None
    assert persisted.status == ApprovalStatus.APPROVED
    assert persisted.response == "apply"
    assert persisted.metadata["approvalScope"] == "workspace"
    assert persisted.metadata["approvalDecision"]["response"] == "apply"
    assert result.response == "apply"


def test_submit_approval_rejects_invalid_scope_or_decision(tmp_path) -> None:
    store = JsonApprovalStore(base_dir=tmp_path)
    approval = store.create(
        session_id="session-5",
        run_id="run-5",
        surface="ws",
        question="Approve export?",
    )

    with pytest.raises(ValueError):
        SubmitApprovalUseCase(store).execute(
            SubmitApprovalRequest(
                approval_id=approval.approval_id,
                decision="allow",
                scope="team",  # type: ignore[arg-type]
            )
        )

    with pytest.raises(ValueError):
        SubmitApprovalUseCase(store).execute(
            {"approvalId": approval.approval_id, "decision": "maybe"}
        )
