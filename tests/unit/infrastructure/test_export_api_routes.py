from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from ds_agent.api.app import create_app
from ds_agent.api.ws_handler import AppState
from ds_agent.config.schema import AgentConfig, DSAgentConfig
from ds_agent.domain.result_card import ResultCardSource, clone_result_card, coerce_result_card
from ds_agent.infrastructure.persistence.card_store import SqliteCardStore

NOW = datetime(2026, 4, 20, 9, 0, tzinfo=UTC)


def _client(tmp_path) -> TestClient:
    app = create_app()
    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
    )
    app.state.app_state = AppState(config=config)
    return TestClient(app)


def _seed_run(
    client: TestClient,
    *,
    session_id: str,
    message: str = "Investigate retention",
) -> str:
    state = client.app.state.app_state
    run = state._runs.create(session_id, "ws", message)
    state._runs.mark_succeeded(run.run_id, "Retention improved", 1.23)
    return run.run_id


def _seed_insight_card(
    client: TestClient,
    *,
    session_id: str,
    card_id: str,
    run_id: str,
    title: str,
    archived: bool = False,
) -> None:
    workspace_dir = client.app.state.app_state.config.agent.workspace_dir
    store = SqliteCardStore.for_workspace(workspace_dir)
    card = coerce_result_card(
        "insight",
        {
            "title": title,
            "evidence": ["cohort analysis"],
            "trustStatus": "partial",
            "quickActions": ["export_report"],
        },
        card_id=card_id,
        result_id=f"result-{card_id}",
        created_at=NOW,
        source=ResultCardSource(messageId=f"msg-{card_id}", runId=run_id),
        archived=archived,
    )
    store.save_card(session_id, clone_result_card(card, archived=archived))


def test_create_app_mounts_export_routes(tmp_path) -> None:
    client = _client(tmp_path)

    paths = {getattr(route, "path", "") for route in client.app.routes}

    assert "/api/export/runs/{run_id}/artifacts" in paths
    assert "/api/export/file" in paths


def test_list_run_artifacts_route_returns_authoritative_payload(tmp_path) -> None:
    client = _client(tmp_path)
    workspace = Path(client.app.state.app_state.config.agent.workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "report.md").write_text("# Report\n", encoding="utf-8")
    (workspace / "metrics.csv").write_text("label,value\nlift,0.12\n", encoding="utf-8")
    (workspace / "plot.png").write_bytes(b"\x89PNG")

    run_id = _seed_run(client, session_id="session-a")
    other_run_id = _seed_run(client, session_id="session-a", message="Other run")
    _seed_insight_card(
        client,
        session_id="session-a",
        card_id="RC-100",
        run_id=run_id,
        title="Primary",
    )
    _seed_insight_card(
        client,
        session_id="session-a",
        card_id="RC-200",
        run_id=other_run_id,
        title="Other run card",
    )

    response = client.get(f"/api/export/runs/{run_id}/artifacts")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == {
        "cards": "run",
        "files": "workspace",
        "exportCandidates": "workspace",
    }
    assert payload["run"]["runId"] == run_id
    assert payload["run"]["sessionId"] == "session-a"
    assert payload["run"]["status"] == "succeeded"
    assert [card["cardId"] for card in payload["cards"]] == ["RC-100"]
    assert payload["summary"]["cardCount"] == 1
    assert payload["summary"]["fileCount"] == 3
    assert payload["summary"]["exportCandidateCount"] == 2
    assert [entry["path"] for entry in payload["files"]] == [
        "metrics.csv",
        "plot.png",
        "report.md",
    ]
    assert payload["exportCandidates"] == [
        {
            "name": "metrics.csv",
            "path": "metrics.csv",
            "type": "csv",
            "formats": ["html", "xlsx"],
        },
        {
            "name": "report.md",
            "path": "report.md",
            "type": "md",
            "formats": ["docx", "html", "pdf"],
        },
    ]


def test_list_run_artifacts_route_returns_404_for_unknown_run(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/export/runs/missing-run/artifacts")

    assert response.status_code == 404
    assert response.json() == {"detail": "Run not found: missing-run"}


def test_export_file_route_reuses_workspace_export_service(tmp_path) -> None:
    client = _client(tmp_path)
    workspace = Path(client.app.state.app_state.config.agent.workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "report.md").write_text("# Export me\n", encoding="utf-8")

    response = client.post(
        "/api/export/file",
        json={"path": "report.md", "format": "html"},
    )

    assert response.status_code == 200
    payload = response.json()["export"]
    exported = Path(payload["exportPath"])
    assert exported.is_file()
    assert payload["format"] == "html"
    assert payload["needsPdfRender"] is False
    assert payload["suggestedFilename"] == "report.html"
    assert payload["audience"] is None


def test_export_file_route_applies_audience_suffix_metadata(tmp_path) -> None:
    client = _client(tmp_path)
    workspace = Path(client.app.state.app_state.config.agent.workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "report.md").write_text("# Export me\n", encoding="utf-8")

    response = client.post(
        "/api/export/file",
        json={"path": "report.md", "format": "html", "audience": "exec"},
    )

    assert response.status_code == 200
    payload = response.json()["export"]
    exported = Path(payload["exportPath"])
    assert exported.is_file()
    assert exported.name == "report.exec.html"
    assert payload["format"] == "html"
    assert payload["needsPdfRender"] is False
    assert payload["suggestedFilename"] == "report.exec.html"
    assert payload["audience"] == "exec"
