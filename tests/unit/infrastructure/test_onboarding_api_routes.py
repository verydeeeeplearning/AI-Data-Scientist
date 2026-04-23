from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ds_agent.api.app import create_app
from ds_agent.api.ws_handler import AppState
from ds_agent.config.schema import AgentConfig, DSAgentConfig, ProviderConfig
from ds_agent.domain.value_objects.use_case_mapping import USE_CASE_SPECS


def _client(tmp_path) -> TestClient:
    app = create_app()
    config = DSAgentConfig(
        provider=ProviderConfig(
            default_model="anthropic/claude-sonnet-4-6",
            fallback_models=["openai/gpt-4.1-mini"],
            max_budget_usd=10.0,
            budget_warning_threshold_pct=80.0,
        ),
        agent=AgentConfig(
            workspace_dir=str(tmp_path / "workspace"),
            mode="supervised",
            language="en",
        ),
    )
    app.state.app_state = AppState(config=config)
    return TestClient(app)


def _full_finalize_payload(*, session_id: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "useCaseId": "prediction",
        "starterPrompt": "Predict customer churn next quarter.",
        "responses": {
            "step1_useCase": "prediction",
            "step2_data": {"type": "sample", "sampleId": "builtin:prediction"},
            "step3_deliverables": ["report", "notebook"],
            "step4_mode": "balanced",
            "step5_model": "anthropic/claude-sonnet-4-6",
            "step6_confirmed": True,
        },
    }
    if session_id is not None:
        payload["sessionId"] = session_id
    return payload


def test_onboarding_finalize_bootstraps_session_and_mission_hydration(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/onboarding/finalize",
        json={
            "responses": {
                "step1_useCase": "reporting",
                "step4_mode": "controlled",
            },
            "unexpectedField": "ignored",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    session_id = payload["sessionId"]
    assert isinstance(session_id, str)
    assert len(session_id) == 8
    assert payload["createdSession"] is True
    assert payload["goalSeeded"] is True
    assert payload["mission"]["goal"]["title"] == (
        "Prepare a reporting-ready analysis with clear takeaways."
    )
    assert payload["mission"]["stage"] == {
        "current": 1,
        "total": 4,
        "label": "Goal captured",
    }
    assert payload["mission"]["mode"] == "supervised"
    assert payload["mission"]["model"]["primary"] == "anthropic/claude-sonnet-4-6"

    sessions = client.app.state.app_state.list_sessions(limit=10)
    assert any(session.session_id == session_id and session.surface == "ws" for session in sessions)

    mission_response = client.get("/api/mission/current", params={"sessionId": session_id})
    assert mission_response.status_code == 200
    assert mission_response.json()["mission"] == payload["mission"]


def test_onboarding_finalize_reuses_existing_session_without_overwriting_goal(tmp_path) -> None:
    client = _client(tmp_path)
    session_id = "existing1"

    first = client.post(
        "/api/onboarding/finalize",
        json={
            "sessionId": session_id,
            "goal": "Investigate churn drivers for the retention team.",
        },
    )
    assert first.status_code == 200
    assert first.json()["createdSession"] is True
    assert first.json()["goalSeeded"] is True

    second = client.post(
        "/api/onboarding/finalize",
        json={
            "sessionId": session_id,
            "goal": "Replace the goal on retry.",
            "useCaseId": "prediction",
        },
    )

    assert second.status_code == 200
    payload = second.json()
    assert payload["sessionId"] == session_id
    assert payload["createdSession"] is False
    assert payload["goalSeeded"] is False
    assert payload["mission"]["goal"]["title"] == (
        "Investigate churn drivers for the retention team."
    )
    assert payload["mission"]["stage"] == {
        "current": 1,
        "total": 4,
        "label": "Goal captured",
    }

    mission_response = client.get("/api/mission/current", params={"sessionId": session_id})
    assert mission_response.status_code == 200
    assert (
        mission_response.json()["mission"]["goal"]["title"] == payload["mission"]["goal"]["title"]
    )


def test_onboarding_finalize_auto_drafts_task_contract_when_flag_enabled(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ONBOARDING_AUTO_DRAFT_CONTRACT_V1", "true")
    client = _client(tmp_path)

    response = client.post("/api/onboarding/finalize", json=_full_finalize_payload())

    assert response.status_code == 200
    payload = response.json()
    session_id = payload["sessionId"]
    task_id = payload["taskId"]
    assert isinstance(task_id, str)
    assert task_id
    assert (
        payload["mission"]["goal"]["title"]
        == "Plan a prediction workflow and define the evaluation approach."
    )
    assert payload["mission"]["stage"] == {
        "current": 1,
        "total": 4,
        "label": "Mission drafting",
    }

    active_response = client.get("/api/task-contracts/active", params={"sessionId": session_id})
    assert active_response.status_code == 200
    contract = active_response.json()["contract"]
    assert contract["contract"]["task_id"] == task_id
    assert contract["contract"]["status"] == "draft"
    assert contract["contract"]["type"] == "prediction"


def test_onboarding_finalize_does_not_auto_draft_task_contract_when_flag_missing(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("ONBOARDING_AUTO_DRAFT_CONTRACT_V1", raising=False)
    client = _client(tmp_path)

    response = client.post("/api/onboarding/finalize", json=_full_finalize_payload())

    assert response.status_code == 200
    payload = response.json()
    session_id = payload["sessionId"]
    assert payload["taskId"] is None

    active_response = client.get("/api/task-contracts/active", params={"sessionId": session_id})
    assert active_response.status_code == 200
    assert active_response.json()["contract"] is None


def test_onboarding_finalize_reuses_existing_draft_task_contract_when_flag_enabled(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ONBOARDING_AUTO_DRAFT_CONTRACT_V1", "true")
    client = _client(tmp_path)
    session_id = "session-flagged"

    first = client.post(
        "/api/onboarding/finalize", json=_full_finalize_payload(session_id=session_id)
    )
    second = client.post(
        "/api/onboarding/finalize", json=_full_finalize_payload(session_id=session_id)
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["taskId"] == second.json()["taskId"]

    contracts = client.get("/api/task-contracts", params={"sessionId": session_id}).json()[
        "contracts"
    ]
    assert len(contracts) == 1


@pytest.mark.parametrize("use_case_id", sorted(USE_CASE_SPECS.keys()))
def test_onboarding_finalize_auto_drafts_contract_for_every_supported_use_case(
    tmp_path,
    monkeypatch,
    use_case_id: str,
) -> None:
    monkeypatch.setenv("ONBOARDING_AUTO_DRAFT_CONTRACT_V1", "true")
    client = _client(tmp_path)

    response = client.post(
        "/api/onboarding/finalize",
        json={
            "useCaseId": use_case_id,
            "starterPrompt": f"Start the {use_case_id} mission.",
            "responses": {
                "step1_useCase": use_case_id,
                "step2_data": {"type": "database_deferred"},
                "step3_deliverables": ["report"],
                "step4_mode": "balanced",
                "step5_model": "anthropic/claude-sonnet-4-6",
                "step6_confirmed": True,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    session_id = payload["sessionId"]
    task_id = payload["taskId"]
    assert isinstance(task_id, str)
    assert task_id

    active_response = client.get("/api/task-contracts/active", params={"sessionId": session_id})
    assert active_response.status_code == 200
    active_payload = active_response.json()["contract"]
    assert active_payload["contract"]["task_id"] == task_id
    assert active_payload["contract"]["status"] == "draft"
    assert active_payload["contract"]["type"] == USE_CASE_SPECS[use_case_id].contract_type
