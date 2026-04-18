from __future__ import annotations

from fastapi.testclient import TestClient

from ds_agent.api.app import create_app
from ds_agent.api.ws_handler import AppState
from ds_agent.application.dtos.task_contract import TaskContractDraftDTO
from ds_agent.application.dtos.work_object import (
    AdvanceWorkObjectPhaseDTO,
    CreateWorkObjectDTO,
    LinkExternalReferenceDTO,
)
from ds_agent.config.schema import AgentConfig, DSAgentConfig
from ds_agent.domain.entities.work_object import WorkObjectPhase
from ds_agent.infrastructure.task_contract_container import build_task_contract_container
from ds_agent.infrastructure.work_object_container import build_work_object_container


def _client(tmp_path) -> TestClient:
    app = create_app()
    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
    )
    app.state.app_state = AppState(config=config)
    return TestClient(app)


def _create_task_contract(workspace_dir: str, session_id: str = "workflow-session-1") -> str:
    container = build_task_contract_container(workspace_dir)
    result = container.create.execute(
        TaskContractDraftDTO(
            session_id=session_id,
            contract_type="churn_analysis",
            business_goal="Reduce churn by one point",
            goal_brief={
                "business_question": "What drives churn?",
                "ds_problem_statement": "Binary classification",
                "comparison_baseline": "last quarter",
                "decision_to_make": "prioritize interventions",
                "expected_effort": "M",
            },
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"}
            ],
        )
    )
    return str(result["task_id"])


def _create_work_object(workspace_dir: str, *, session_id: str = "workflow-session-1") -> str:
    task_id = _create_task_contract(workspace_dir, session_id=session_id)
    container = build_work_object_container(workspace_dir)
    view = container.create.execute(
        CreateWorkObjectDTO(
            task_contract_id=task_id,
            title="Retention workflow",
            request_source="slack",
            requestor_id="U123",
            requestor_display="Kim",
            original_text="Investigate churn and prepare follow-up actions.",
            channel="growth-ds",
        )
    )
    container.attach_reference.execute(
        LinkExternalReferenceDTO(
            work_object_id=view.work_object.work_object_id,
            system="confluence",
            resource_type="page",
            resource_id="page-1",
            location="documentation",
            description="Executive brief page",
        )
    )
    return view.work_object.work_object_id


def test_list_work_objects_route_filters_by_session(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    work_object_id = _create_work_object(workspace_dir, session_id="renderer-session")

    response = client.get(
        "/api/work-objects",
        params={"sessionId": "renderer-session", "limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["work_objects"][0]["work_object_id"] == work_object_id
    assert payload["work_objects"][0]["phase"] == "intake"


def test_get_work_object_route_returns_timeline_and_references(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    work_object_id = _create_work_object(workspace_dir)

    response = client.get(
        f"/api/work-objects/{work_object_id}",
        params={"timelineLimit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["work_object"]["work_object_id"] == work_object_id
    assert payload["work_object"]["documentation"]["references"][0]["resource_id"] == "page-1"
    assert len(payload["timeline"]) >= 2


def test_get_work_object_route_returns_not_found(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/work-objects/WO-2026-9999")

    assert response.status_code == 404


def test_intake_work_object_route_creates_from_jira_request(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    task_id = _create_task_contract(workspace_dir, session_id="jira-session")

    response = client.post(
        "/api/work-objects/intake",
        json={
            "taskContractId": task_id,
            "title": "Retention escalation",
            "requestSource": "jira",
            "requestorId": "analyst@example.com",
            "requestorDisplay": "Analyst Kim",
            "originalText": "Please investigate churn spikes and propose actions.",
            "channel": "DS-17",
            "requestMetadata": {"priority": "high", "segment": "enterprise"},
            "externalReference": {
                "system": "jira",
                "resource_type": "issue",
                "resource_id": "DS-17",
                "url": "https://jira.local/browse/DS-17",
            },
            "tags": ["retention", "escalation"],
        },
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["work_object"]["execution"]["task_contract_id"] == task_id
    assert payload["work_object"]["request"]["source"] == "jira"
    assert payload["work_object"]["request"]["metadata"]["priority"] == "high"
    assert payload["work_object"]["request"]["external_ref"]["resource_id"] == "DS-17"
    assert (
        ":jira:intake_request:"
        in payload["work_object"]["request"]["external_ref"]["idempotency_key"]
    )


def test_advance_work_object_phase_route_records_run_and_timeline(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    work_object_id = _create_work_object(workspace_dir)

    response = client.post(
        f"/api/work-objects/{work_object_id}/phase",
        json={"toPhase": "executing", "runId": "run-17"},
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["work_object_id"] == work_object_id
    assert payload["phase"] == WorkObjectPhase.EXECUTING.value
    assert payload["run_ids"] == ["run-17"]

    timeline = client.get(f"/api/work-objects/{work_object_id}/timeline", params={"limit": 10})

    assert timeline.status_code == 200
    assert any(
        event["action"] == "advance_phase" and event["status"] == "success"
        for event in timeline.json()["events"]
    )


def test_close_work_object_route_closes_ready_follow_up(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    work_object_id = _create_work_object(workspace_dir)
    container = build_work_object_container(workspace_dir)

    container.advance_phase.execute(
        AdvanceWorkObjectPhaseDTO(
            work_object_id=work_object_id,
            to_phase=WorkObjectPhase.EXECUTING,
        )
    )
    container.advance_phase.execute(
        AdvanceWorkObjectPhaseDTO(
            work_object_id=work_object_id,
            to_phase=WorkObjectPhase.REVIEW,
        )
    )
    container.advance_phase.execute(
        AdvanceWorkObjectPhaseDTO(
            work_object_id=work_object_id,
            to_phase=WorkObjectPhase.DOCUMENTING,
        )
    )
    container.advance_phase.execute(
        AdvanceWorkObjectPhaseDTO(
            work_object_id=work_object_id,
            to_phase=WorkObjectPhase.FOLLOWUP,
        )
    )
    container.attach_reference.execute(
        LinkExternalReferenceDTO(
            work_object_id=work_object_id,
            system="slack",
            resource_type="message",
            resource_id="1700000000.1",
            location="follow_up",
            action_type="message",
            description="Stakeholder notified",
            metadata={"status": "completed"},
        )
    )

    response = client.post(
        f"/api/work-objects/{work_object_id}/close",
        json={"reason": "handoff complete"},
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["phase"] == WorkObjectPhase.CLOSED.value
    assert payload["close_reason"] == "handoff complete"
