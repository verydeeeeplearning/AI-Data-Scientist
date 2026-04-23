"""Unit tests for the approval grant use cases (W2-F phase 2)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from ds_agent.application.use_cases.approval_grant_usecases import (
    IssueApprovalGrantInput,
    IssueApprovalGrantUseCase,
    ListApprovalGrantsUseCase,
    RevokeApprovalGrantUseCase,
)
from ds_agent.domain.entities.approval_grant import (
    DEFAULT_SESSION_TIMEOUT_SECONDS,
    ApprovalGrantScope,
)
from ds_agent.runtime.approval_grant_store import JsonApprovalGrantStore


@pytest.fixture()
def store(tmp_path: Path) -> JsonApprovalGrantStore:
    return JsonApprovalGrantStore(base_dir=tmp_path)


def _issue_session_grant(store: JsonApprovalGrantStore) -> object:
    use_case = IssueApprovalGrantUseCase(store)
    return use_case.execute(
        IssueApprovalGrantInput(
            approval_id="appr-1",
            scope=ApprovalGrantScope.SESSION,
            risk_code="PAT_FILESYSTEM_WRITE",
            kind="generic",
            session_id="sess-1",
            workspace_id="/tmp/workspace",
            actor="electron",
            source="electron",
            affected_scopes=["filesystem"],
        )
    )


def test_issue_session_grant_persists_with_default_timeout(
    store: JsonApprovalGrantStore,
) -> None:
    grant = _issue_session_grant(store)
    assert grant.scope == ApprovalGrantScope.SESSION
    assert grant.expires_at is not None
    assert grant.expires_at - grant.created_at == pytest.approx(
        DEFAULT_SESSION_TIMEOUT_SECONDS, rel=1e-3
    )


def test_issue_workspace_grant_has_no_expiry(store: JsonApprovalGrantStore) -> None:
    use_case = IssueApprovalGrantUseCase(store)
    grant = use_case.execute(
        IssueApprovalGrantInput(
            approval_id="appr-2",
            scope=ApprovalGrantScope.WORKSPACE,
            risk_code="PAT_NETWORK_OUT",
            kind="generic",
            session_id="sess-2",
            workspace_id="/tmp/workspace",
            actor="electron",
            source="electron",
            affected_scopes=["network"],
        )
    )
    assert grant.scope == ApprovalGrantScope.WORKSPACE
    assert grant.expires_at is None


def test_list_active_grants_filters_revoked(store: JsonApprovalGrantStore) -> None:
    grant_a = _issue_session_grant(store)
    grant_b = _issue_session_grant(store)
    revoke_use_case = RevokeApprovalGrantUseCase(store)
    revoke_use_case.execute(grant_a.grant_id, actor="settings-ui")

    list_use_case = ListApprovalGrantsUseCase(store)
    grants = list_use_case.execute()
    grant_ids = [item["grantId"] for item in grants]
    assert grant_b.grant_id in grant_ids
    assert grant_a.grant_id not in grant_ids


def test_revoke_unknown_raises_lookup_error(store: JsonApprovalGrantStore) -> None:
    use_case = RevokeApprovalGrantUseCase(store)
    with pytest.raises(LookupError):
        use_case.execute("does-not-exist")


def test_find_active_match_respects_session_isolation(
    store: JsonApprovalGrantStore,
) -> None:
    _issue_session_grant(store)
    other_session = store.find_active_match(
        risk_code="PAT_FILESYSTEM_WRITE",
        session_id="other-session",
        workspace_id="/tmp/workspace",
    )
    assert other_session is None
    same_session = store.find_active_match(
        risk_code="PAT_FILESYSTEM_WRITE",
        session_id="sess-1",
        workspace_id="/tmp/workspace",
    )
    assert same_session is not None


def test_session_grant_expires_after_timeout(store: JsonApprovalGrantStore) -> None:
    use_case = IssueApprovalGrantUseCase(store)
    grant = use_case.execute(
        IssueApprovalGrantInput(
            approval_id="appr-3",
            scope=ApprovalGrantScope.SESSION,
            risk_code="PAT_SUBPROCESS_SPAWN",
            kind="generic",
            session_id="sess-3",
            workspace_id="/tmp/workspace",
            actor="electron",
            source="electron",
            affected_scopes=["subprocess"],
            session_ttl_seconds=1.0,
        )
    )
    expired_clock = time.time() + 5.0
    assert grant.is_active() is True
    assert grant.is_active(now=expired_clock) is False


def test_issue_requires_approval_id(store: JsonApprovalGrantStore) -> None:
    use_case = IssueApprovalGrantUseCase(store)
    with pytest.raises(ValueError):
        use_case.execute(
            IssueApprovalGrantInput(
                approval_id="",
                scope=ApprovalGrantScope.SESSION,
                risk_code="PAT",
                kind="generic",
                session_id="sess",
            )
        )
