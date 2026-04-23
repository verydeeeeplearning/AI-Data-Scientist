"""HTTP integration tests for approval grant routes (W2-F phase 2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ds_agent.api.app import create_app
from ds_agent.application.use_cases.approval_grant_usecases import (
    IssueApprovalGrantInput,
    IssueApprovalGrantUseCase,
)
from ds_agent.domain.entities.approval_grant import ApprovalGrantScope


@pytest.fixture()
def client_with_grants(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DS_AGENT_WORKSPACE", str(tmp_path))
    app = create_app(ws_token=None)
    client = TestClient(app)
    with client:
        # Lifespan starts; AppState is constructed lazily.
        store = app.state.app_state.approval_grant_store
        IssueApprovalGrantUseCase(store).execute(
            IssueApprovalGrantInput(
                approval_id="appr-route-1",
                scope=ApprovalGrantScope.SESSION,
                risk_code="PAT_NETWORK_OUT",
                kind="generic",
                session_id="sess-route-1",
                workspace_id=str(tmp_path),
                actor="electron",
                source="electron",
                affected_scopes=["network"],
            )
        )
        yield client


def test_list_route_returns_active_grants(client_with_grants: TestClient) -> None:
    response = client_with_grants.get("/api/approval/grants")
    assert response.status_code == 200
    payload = response.json()
    assert "grants" in payload
    assert any(grant["riskCode"] == "PAT_NETWORK_OUT" for grant in payload["grants"])


def test_revoke_route_marks_grant_revoked(client_with_grants: TestClient) -> None:
    list_response = client_with_grants.get("/api/approval/grants").json()
    grant = next(
        (entry for entry in list_response["grants"] if entry["riskCode"] == "PAT_NETWORK_OUT"),
        None,
    )
    assert grant is not None
    grant_id = grant["grantId"]

    revoke_response = client_with_grants.post(
        f"/api/approval/grants/{grant_id}/revoke"
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["grant"]["status"] == "revoked"

    after_active = client_with_grants.get("/api/approval/grants").json()
    assert all(entry["grantId"] != grant_id for entry in after_active["grants"])

    after_inactive = client_with_grants.get(
        "/api/approval/grants?includeInactive=true"
    ).json()
    assert any(entry["grantId"] == grant_id for entry in after_inactive["grants"])


def test_revoke_unknown_returns_404(client_with_grants: TestClient) -> None:
    response = client_with_grants.post("/api/approval/grants/does-not-exist/revoke")
    assert response.status_code == 404
