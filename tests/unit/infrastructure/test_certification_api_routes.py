from __future__ import annotations

from fastapi.testclient import TestClient

from ds_agent.api.app import create_app
from ds_agent.api.ws_handler import AppState
from ds_agent.config.schema import AgentConfig, DSAgentConfig
from ds_agent.domain.entities.certification import AutonomyRunStat
from ds_agent.infrastructure.persistence.certification_store import SqliteCertificationStore


def _client(tmp_path) -> TestClient:
    app = create_app()
    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
    )
    app.state.app_state = AppState(config=config)
    return TestClient(app)


def _seed_ready_stats(workspace_dir: str) -> None:
    store = SqliteCertificationStore.for_workspace(workspace_dir)
    for index in range(10):
        store.record_run_stat(
            AutonomyRunStat(
                mission_name="weekly-kpi-triage",
                mission_version=1,
                run_id=f"run-{index}",
                authority="shadow",
                audience="senior_staff",
                started_at="2026-04-01T00:00:00Z",
                ended_at="2026-04-01T00:10:00Z",
                outcome="success",
                verifier_score=0.90,
                rollback_rehearsal=index == 0,
            )
        )


def test_list_certification_statuses_returns_available_missions(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    _seed_ready_stats(workspace_dir)

    response = client.get("/api/certification")

    assert response.status_code == 200
    payload = response.json()
    mission = payload["missions"][0]
    assert mission["mission_name"] == "weekly-kpi-triage"
    assert mission["stats"]["shadow_runs_passed"] == 10
    assert mission["next_target"] == "autopilot"


def test_get_certification_status_route_returns_snapshot(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    _seed_ready_stats(workspace_dir)

    response = client.get("/api/certification/weekly-kpi-triage")

    assert response.status_code == 200
    mission = response.json()["mission"]
    assert mission["effective_level"] == "delegate"
    assert mission["required_approvers"] == 2
    assert mission["gaps"] == []


def test_submit_certification_route_persists_record(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    _seed_ready_stats(workspace_dir)

    response = client.post(
        "/api/certification/weekly-kpi-triage/submit",
        json={
            "targetLevel": "autopilot",
            "approvedBy": ["owner-park", "owner-cho"],
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "certified"
    assert result["target_level"] == "autopilot"
    store = SqliteCertificationStore.for_workspace(workspace_dir)
    assert store.is_certified("weekly-kpi-triage", "autopilot", mission_version=1) is True


def test_submit_certification_route_returns_not_found_for_unknown_mission(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/certification/unknown-mission/submit",
        json={
            "targetLevel": "autopilot",
            "approvedBy": ["owner-park"],
        },
    )

    assert response.status_code == 404
