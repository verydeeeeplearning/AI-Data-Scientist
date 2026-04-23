from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ds_agent.api.app import create_app
from ds_agent.api.ws_handler import AppState
from ds_agent.config.schema import AgentConfig, DSAgentConfig


def _client(tmp_path) -> TestClient:
    app = create_app()
    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
    )
    app.state.app_state = AppState(config=config)
    return TestClient(app)


def test_workspace_upload_route_returns_schema_preview_and_saves_file(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/workspace/upload?headRows=1000&sampleRows=3",
        files={
            "file": (
                "customers.csv",
                "\n".join(
                    [
                        "customer_id,churn,monthly_spend",
                        "1,0,10",
                        "2,1,12",
                        "3,0,999",
                    ]
                ).encode("utf-8"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()["preview"]
    assert payload["fileName"] == "customers.csv"
    assert payload["workspacePath"] == "customers.csv"
    assert payload["format"] == "csv"
    assert payload["sampleRows"][0]["customer_id"] == 1
    assert payload["suggestedTarget"]["columnName"] == "churn"
    saved = Path(client.app.state.app_state.config.agent.workspace_dir) / "customers.csv"
    assert saved.exists()


def test_workspace_upload_route_deduplicates_existing_filenames(tmp_path) -> None:
    client = _client(tmp_path)

    first = client.post(
        "/api/workspace/upload",
        files={"file": ("dataset.csv", b"target\n1\n0\n", "text/csv")},
    )
    second = client.post(
        "/api/workspace/upload",
        files={"file": ("dataset.csv", b"target\n0\n1\n", "text/csv")},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["preview"]["workspacePath"] == "dataset.csv"
    assert second.json()["preview"]["workspacePath"] == "dataset-1.csv"


def test_workspace_upload_route_rejects_unsafe_extension(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/workspace/upload",
        files={"file": ("payload.exe", b"MZ\x00\x00", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "File type not allowed" in response.json()["detail"]


def test_workspace_upload_route_rejects_disguised_binary_text_upload(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/workspace/upload",
        files={"file": ("payload.csv", b"MZ\x90\x00not-a-csv", "text/csv")},
    )

    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "signature" in detail or "nul bytes" in detail
    saved = Path(client.app.state.app_state.config.agent.workspace_dir) / "payload.csv"
    assert not saved.exists()
