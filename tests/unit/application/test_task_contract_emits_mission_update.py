"""Verify that task contract updates trigger a mission.context.updated broadcast."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from ds_agent.api.app import create_app
from ds_agent.api.ws_handler import AppState
from ds_agent.config.schema import AgentConfig, DSAgentConfig, ProviderConfig
from ds_agent.domain.entities.dataset_manifest import DatasetEntry, DatasetManifest
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.task_contract import DefinitionOfDone, TaskContract
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore


def _client(tmp_path):
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


def _seed_bundle(client: TestClient, *, session_id: str, task_id: str) -> int:
    now = datetime(2026, 4, 19, tzinfo=UTC)
    bundle = TaskContractBundle(
        contract=TaskContract(
            task_id=task_id,
            session_id=session_id,
            type="churn_analysis",
            status="in_progress",
            business_goal="Reduce churn",
            authority="supervised",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"}
            ],
            definition_of_done=DefinitionOfDone(criteria=["Quantify churn drivers."]),
            created_at=now,
            updated_at=now,
        ),
        goal_brief=GoalBrief(
            brief_id="GB-3",
            task_id=task_id,
            business_question="Why is churn rising?",
            ds_problem_statement="Estimate churn drivers.",
            comparison_baseline="last quarter",
            decision_to_make="Choose retention action",
            expected_effort="M",
            created_at=now,
            updated_at=now,
        ),
        dataset_manifest=DatasetManifest(
            manifest_id="DM-3",
            task_id=task_id,
            entries=[DatasetEntry(dataset_ref="uploads/churn.csv", row_count=321)],
            total_rows=321,
            generated_at=now,
        ),
    ).sync_references()
    workspace_dir = client.app.state.app_state.config.agent.workspace_dir
    SqliteTaskContractStore.for_workspace(workspace_dir).create_bundle(bundle)
    return bundle.contract.version


def test_task_contract_update_broadcasts_mission_event(tmp_path) -> None:
    client = _client(tmp_path)
    session_id = "session-emission"
    task_id = "TC-2026-100"
    version = _seed_bundle(client, session_id=session_id, task_id=task_id)

    received: list[tuple[str, dict]] = []

    def listener(event: str, payload: dict) -> None:
        received.append((event, payload))

    client.app.state.app_state.register_runtime_listener(listener)

    response = client.post(
        f"/api/task-contracts/{task_id}/update",
        json={
            "expectedVersion": version,
            "patch": {"business_goal": "Reduce churn for premium users"},
        },
    )
    assert response.status_code == 200, response.text

    mission_events = [item for item in received if item[0] == "mission.context.updated"]
    assert len(mission_events) == 1
    payload = mission_events[0][1]
    assert payload["sessionId"] == session_id
    assert payload["goal"]["title"] == "Reduce churn for premium users"


def test_task_contract_update_skips_broadcast_for_unrelated_patch(tmp_path) -> None:
    client = _client(tmp_path)
    session_id = "session-skip"
    task_id = "TC-2026-101"
    version = _seed_bundle(client, session_id=session_id, task_id=task_id)

    received: list[tuple[str, dict]] = []
    client.app.state.app_state.register_runtime_listener(
        lambda event, payload: received.append((event, payload))
    )

    response = client.post(
        f"/api/task-contracts/{task_id}/update",
        json={
            "expectedVersion": version,
            "patch": {"primary_kpi_id": "kpi-revenue"},
        },
    )
    assert response.status_code == 200, response.text

    mission_events = [item for item in received if item[0] == "mission.context.updated"]
    assert mission_events == []


def test_pause_endpoint_broadcasts_mission_event(tmp_path) -> None:
    client = _client(tmp_path)
    session_id = "session-pause"
    received: list[tuple[str, dict]] = []
    client.app.state.app_state.register_runtime_listener(
        lambda event, payload: received.append((event, payload))
    )

    response = client.post(
        "/api/mission/pause",
        json={"sessionId": session_id, "reason": "budget_warning"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["paused"] is False
    assert body["previousStatus"] == "idle"

    mission_events = [item for item in received if item[0] == "mission.context.updated"]
    assert len(mission_events) == 1
    assert mission_events[0][1]["sessionId"] == session_id


def test_task_contract_update_includes_delta_for_data_sources(tmp_path) -> None:
    client = _client(tmp_path)
    session_id = "session-delta"
    task_id = "TC-2026-102"
    version = _seed_bundle(client, session_id=session_id, task_id=task_id)

    received: list[tuple[str, dict]] = []
    client.app.state.app_state.register_runtime_listener(
        lambda event, payload: received.append((event, payload))
    )

    response = client.post(
        f"/api/task-contracts/{task_id}/update",
        json={
            "expectedVersion": version,
            "patch": {
                "allowed_data_sources": [
                    {
                        "warehouse": "warehouse_main",
                        "schema_name": "analytics",
                        "purpose": "exploration",
                    }
                ]
            },
        },
    )
    assert response.status_code == 200, response.text

    mission_events = [item for item in received if item[0] == "mission.context.updated"]
    assert len(mission_events) == 1
    payload = mission_events[0][1]
    assert payload["sessionId"] == session_id
    assert "delta" in payload
    assert payload["delta"].get("dataSources") is True


def test_task_contract_update_omits_delta_when_fields_untouched(tmp_path) -> None:
    client = _client(tmp_path)
    session_id = "session-no-delta"
    task_id = "TC-2026-103"
    version = _seed_bundle(client, session_id=session_id, task_id=task_id)

    received: list[tuple[str, dict]] = []
    client.app.state.app_state.register_runtime_listener(
        lambda event, payload: received.append((event, payload))
    )

    response = client.post(
        f"/api/task-contracts/{task_id}/update",
        json={
            "expectedVersion": version,
            "patch": {"business_goal": "Reduce churn for SMB"},
        },
    )
    assert response.status_code == 200, response.text

    mission_events = [item for item in received if item[0] == "mission.context.updated"]
    assert len(mission_events) == 1
    assert "delta" not in mission_events[0][1]


def test_pause_endpoint_rejects_blank_session() -> None:
    from fastapi.testclient import TestClient as _TC

    app = create_app()
    app.state.app_state = AppState()
    client = _TC(app)
    response = client.post(
        "/api/mission/pause",
        json={"sessionId": "   ", "reason": "manual"},
    )
    assert response.status_code in {400, 422}
