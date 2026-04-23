from __future__ import annotations

from fastapi.testclient import TestClient

from ds_agent.api.app import create_app
from ds_agent.api.ws_handler import AppState
from ds_agent.config.schema import AgentConfig, DSAgentConfig
from tests.unit.application.test_get_trust_metadata_usecase import _seed_trust_workspace


def _client(tmp_path) -> TestClient:
    app = create_app()
    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
    )
    app.state.app_state = AppState(config=config)
    return TestClient(app)


def test_create_app_mounts_trust_route(tmp_path) -> None:
    client = _client(tmp_path)

    trust_paths = {
        getattr(route, "path", "")
        for route in client.app.routes
    }

    assert "/api/trust/{result_id}" in trust_paths


def test_get_trust_route_returns_projected_metadata(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    result_id = "result-001"
    evidence = _seed_trust_workspace(workspace_dir, result_id)

    response = client.get(f"/api/trust/{result_id}")

    assert response.status_code == 200
    payload = response.json()["trust"]
    assert payload["resultId"] == result_id
    assert payload["verifier"]["status"] == "yellow"
    assert payload["lineage"]["ancestorCount"] == 1
    assert payload["fallback"]["fallbackId"] == evidence["fallback_event_id"]
    assert payload["fallback"]["eventCount"] == 1
    assert payload["fallback"]["status"] == "warning"
    assert payload["fallback"]["summary"] == "anthropic/claude-sonnet-4-6 -> openai/gpt-4.1"
    assert payload["approval"]["approvalId"]
    assert payload["approval"]["approvalStatus"] == "approved"
    assert payload["sandbox"]["violationOccurred"] is True
    assert payload["sandbox"]["eventId"] == evidence["sandbox_event_id"]
    assert payload["sandbox"]["eventCount"] == 1
    assert payload["sandbox"]["summary"] == "code_execution: Sandbox blocked subprocess"
    assert payload["certification"]["level"] == "platinum"


def test_get_trust_route_returns_404_for_unknown_result(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/trust/missing-result")

    assert response.status_code == 404
