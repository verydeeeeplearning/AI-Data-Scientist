from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from ds_agent.api.app import create_app
from ds_agent.api.ws_handler import AppState
from ds_agent.config.schema import AgentConfig, DSAgentConfig
from ds_agent.domain.access.access_log_entry import AccessLogEntry


def _client(tmp_path: Path) -> TestClient:
    app = create_app()
    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
    )
    app.state.app_state = AppState(config=config)
    return TestClient(app)


def test_list_access_log_returns_filtered_entries_for_owner(tmp_path: Path) -> None:
    client = _client(tmp_path)
    store = client.app.state.app_state.access_log_store
    now = time.time()
    store.append(
        AccessLogEntry(
            resource_type="run",
            resource_id="run-old",
            action="view",
            actor_ref="user:111",
            allowed=True,
            reason="allowed",
            created_at=now - 2_000,
        )
    )
    target = AccessLogEntry(
        resource_type="run",
        resource_id="run-target",
        action="export",
        actor_ref="user:222",
        allowed=False,
        reason="denied",
        created_at=now - 1_000,
    )
    store.append(target)
    store.append(
        AccessLogEntry(
            resource_type="artifact",
            resource_id="artifact-1",
            action="view",
            actor_ref="user:333",
            allowed=True,
            reason="allowed",
            created_at=now - 500,
        )
    )

    response = client.get(
        "/api/access-log",
        params={
            "operatorId": "local-user",
            "resourceType": "run",
            "since": now - 1_500,
            "until": now - 500,
            "limit": 10,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert list(body.keys()) == ["entries"]
    assert len(body["entries"]) == 1
    entry = body["entries"][0]
    assert entry["entryId"] == target.entry_id
    assert entry["resourceType"] == "run"
    assert entry["resourceId"] == "run-target"
    assert entry["action"] == "export"
    assert entry["actorRef"] == "user:222"
    assert entry["allowed"] is False
    assert entry["reason"] == "denied"


def test_list_access_log_returns_empty_for_non_owner(tmp_path: Path) -> None:
    client = _client(tmp_path)
    store = client.app.state.app_state.access_log_store
    store.append(
        AccessLogEntry(
            resource_type="run",
            resource_id="run-1",
            action="view",
            actor_ref="user:111",
            allowed=True,
            created_at=time.time() - 100,
        )
    )

    response = client.get(
        "/api/access-log",
        params={
            "operatorId": "viewer-1",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"entries": []}
