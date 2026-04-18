"""True E2E WebSocket tests — WS connect → RPC → agent → response (6.5).

Uses Starlette's TestClient WebSocket support to exercise the full stack:
FastAPI app → WsRpcHandler → AppState → DSAgent → tool dispatch → response.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.testclient import TestClient

from ds_agent.api.app import create_app
from ds_agent.config.schema import DSAgentConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rpc_frame(method: str, params: dict | None = None) -> dict:
    """Build a WS RPC request frame."""
    return {
        "type": "req",
        "id": str(uuid.uuid4())[:8],
        "method": method,
        "params": params or {},
    }


def _recv_until(ws: Any, predicate: Any, *, timeout: float = 5.0) -> dict:
    """Receive WS frames until *predicate* matches or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        data = ws.receive_json()
        if predicate(data):
            return data
    raise TimeoutError("Timed out waiting for matching WS frame")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Provide a temporary workspace directory for the agent."""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    return ws_dir


@pytest.fixture
def test_config(workspace: Path) -> DSAgentConfig:
    """Create a minimal test config."""
    cfg = DSAgentConfig()
    cfg.agent.workspace_dir = str(workspace)
    cfg.agent.max_iterations = 3
    cfg.provider.max_budget_usd = 1.0
    return cfg


@pytest.fixture
def app(test_config: DSAgentConfig):
    """Create FastAPI app with token auth disabled."""
    application = create_app(ws_token=None)
    # Override AppState with test config
    from ds_agent.api.ws_handler import AppState

    application.state.app_state = AppState(config=test_config)
    return application


@pytest.fixture
def client(app: Any) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# E2E Test: config RPC round-trip
# ---------------------------------------------------------------------------


class TestConfigRpcE2E:
    """config.get / config.set via WebSocket — full round-trip."""

    def test_config_get(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(_rpc_frame("config.get"))
            res = ws.receive_json()

            assert res["type"] == "res"
            assert res["ok"] is True
            assert "config" in res["payload"]
            assert "provider" in res["payload"]["config"]

    def test_config_set_and_verify(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            # Set budget
            ws.send_json(
                _rpc_frame("config.set", {"path": "provider.max_budget_usd", "value": 25.0})
            )
            res = ws.receive_json()
            assert res["ok"] is True

            # Verify change
            ws.send_json(_rpc_frame("config.get"))
            res = ws.receive_json()
            assert res["payload"]["config"]["provider"]["max_budget_usd"] == 25.0

    def test_config_set_invalid_path(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(_rpc_frame("config.set", {"path": "nonexistent.path", "value": "x"}))
            res = ws.receive_json()
            assert res["ok"] is False
            assert "INVALID_PARAMS" in res["error"]["code"]


# ---------------------------------------------------------------------------
# E2E Test: files RPC
# ---------------------------------------------------------------------------


class TestFilesRpcE2E:
    """files.list via WebSocket."""

    def test_files_list_empty(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(_rpc_frame("files.list"))
            res = ws.receive_json()
            assert res["ok"] is True
            assert isinstance(res["payload"]["files"], list)

    def test_files_list_with_data(self, client: TestClient, workspace: Path) -> None:
        (workspace / "iris.csv").write_text("a,b,c\n1,2,3")
        with client.websocket_connect("/ws") as ws:
            ws.send_json(_rpc_frame("files.list"))
            res = ws.receive_json()
            assert res["ok"] is True
            files = res["payload"]["files"]
            assert any(f["name"] == "iris.csv" for f in files)
            # New: list entries carry modifiedAt (ms) so the frontend can sort
            entry = next(f for f in files if f["name"] == "iris.csv")
            assert "modifiedAt" in entry and entry["modifiedAt"] > 0

    def test_files_preview_csv(self, client: TestClient, workspace: Path) -> None:
        (workspace / "iris.csv").write_text(
            "sepal_len,sepal_wid,species\n5.1,3.5,setosa\n4.9,3.0,setosa\n"
        )
        with client.websocket_connect("/ws") as ws:
            ws.send_json(_rpc_frame("files.preview", {"path": "iris.csv", "rows": 1}))
            res = ws.receive_json()
            assert res["ok"] is True
            payload = res["payload"]
            assert payload["kind"] == "table"
            assert payload["columns"] == ["sepal_len", "sepal_wid", "species"]
            assert payload["previewRows"] == 1
            assert payload["totalRows"] == 2
            assert payload["rowCount"] == 2
            assert payload["encodingDetected"] == "UTF-8"
            assert len(payload["columnProfiles"]) == 3

    def test_files_preview_text(self, client: TestClient, workspace: Path) -> None:
        (workspace / "report.md").write_text("# Report\n\nBody")
        with client.websocket_connect("/ws") as ws:
            ws.send_json(_rpc_frame("files.preview", {"path": "report.md"}))
            res = ws.receive_json()
            assert res["ok"] is True
            assert res["payload"]["kind"] == "text"
            assert res["payload"]["content"].startswith("# Report")

    def test_files_preview_excel_with_sheet_options(
        self, client: TestClient, workspace: Path
    ) -> None:
        pd = pytest.importorskip("pandas")
        workbook = workspace / "sales.xlsx"
        with pd.ExcelWriter(workbook) as writer:
            pd.DataFrame({"note": ["metadata"]}).to_excel(writer, sheet_name="Summary", index=False)
            pd.DataFrame(
                [
                    ["report generated", ""],
                    ["region", "sales"],
                    ["APAC", 12],
                    ["NA", 18],
                ]
            ).to_excel(writer, sheet_name="Data", index=False, header=False)

        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                _rpc_frame(
                    "files.preview",
                    {
                        "path": "sales.xlsx",
                        "rows": 2,
                        "sheetName": "Data",
                        "headerRow": 2,
                    },
                )
            )
            res = ws.receive_json()
            assert res["ok"] is True
            payload = res["payload"]
            assert payload["kind"] == "table"
            assert payload["selectedSheet"] == "Data"
            assert payload["headerRow"] == 2
            assert payload["sheetNames"] == ["Summary", "Data"]
            assert payload["columns"] == ["region", "sales"]
            assert payload["rows"][0] == ["APAC", "12"]

    def test_files_preview_traversal_rejected(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(_rpc_frame("files.preview", {"path": "../../etc/passwd"}))
            res = ws.receive_json()
            assert res["ok"] is False

    def test_files_delete_removes_file(self, client: TestClient, workspace: Path) -> None:
        target = workspace / "scratch.csv"
        target.write_text("x,y\n1,2")
        with client.websocket_connect("/ws") as ws:
            ws.send_json(_rpc_frame("files.delete", {"path": "scratch.csv"}))
            # The handler fires two fire-and-forget events + one response;
            # collect until we see the response frame.
            res = _recv_until(ws, lambda d: d.get("type") == "res")
            assert res["ok"] is True
            assert res["payload"]["kind"] == "file"
        assert not target.exists()

    def test_files_delete_traversal_rejected(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(_rpc_frame("files.delete", {"path": "../../etc/passwd"}))
            res = _recv_until(ws, lambda d: d.get("type") == "res")
            assert res["ok"] is False

    def test_files_delete_missing_file(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(_rpc_frame("files.delete", {"path": "nope.csv"}))
            res = _recv_until(ws, lambda d: d.get("type") == "res")
            assert res["ok"] is False


class TestConnectorRpcE2E:
    def test_connector_save_list_delete_round_trip(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                _rpc_frame(
                    "connector.save",
                    {
                        "name": "analytics_prod",
                        "type": "postgres",
                        "label": "Analytics Postgres",
                        "options": {
                            "host": "localhost",
                            "database": "analytics",
                            "schema": "public",
                            "username": "readonly_user",
                        },
                        "credentialMethod": "secret_manager",
                        "credentialPayload": {
                            "kind": "password",
                            "password": "secret",
                        },
                    },
                )
            )
            save_res = ws.receive_json()
            assert save_res["ok"] is True
            assert save_res["payload"]["connector"]["name"] == "analytics_prod"

            ws.send_json(_rpc_frame("connector.list"))
            list_res = ws.receive_json()
            assert list_res["ok"] is True
            assert list_res["payload"]["connectors"][0]["hasCredential"] is True

            ws.send_json(_rpc_frame("connector.delete", {"name": "analytics_prod"}))
            delete_res = ws.receive_json()
            assert delete_res["ok"] is True
            assert delete_res["payload"]["deleted"] is True

    def test_connector_test_uses_read_only_probe(self, client: TestClient, app: Any) -> None:
        class FakeConnectorAdapter:
            def execute_query(self, spec: Any) -> list[dict[str, int]]:
                assert spec.sql == "SELECT 1"
                return [{"value": 1}]

        app.state.app_state._connector_adapter_factory = lambda _config: FakeConnectorAdapter()

        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                _rpc_frame(
                    "connector.test",
                    {
                        "name": "analytics_prod",
                        "type": "postgres",
                        "options": {
                            "host": "localhost",
                            "database": "analytics",
                        },
                        "credentialMethod": "secret_manager",
                        "credentialPayload": {
                            "kind": "password",
                            "password": "secret",
                        },
                    },
                )
            )
            res = ws.receive_json()
            assert res["ok"] is True
            assert res["payload"]["ok"] is True
            assert res["payload"]["probe"]["kind"] == "select_1"


# ---------------------------------------------------------------------------
# E2E Test: chat.send → agent.done
# ---------------------------------------------------------------------------


class TestChatE2E:
    """chat.send → agent run → stream.done — full agent turn via WS."""

    def test_chat_send_returns_session_and_done(
        self, client: TestClient, app: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Send a message, get sessionId, then receive stream.done event."""
        # Patch AgentSessionRegistry._create_agent to return a mock agent
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Test analysis complete.")
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.05
        mock_agent._callbacks = None
        mock_agent._history = []

        def _fake_create_agent(
            session_id, callbacks, model=None, *, authority_mode=None, **kwargs
        ):
            return mock_agent

        monkeypatch.setattr(
            app.state.app_state._sessions,
            "_create_agent",
            _fake_create_agent,
        )

        with client.websocket_connect("/ws") as ws:
            # Send chat message
            ws.send_json(_rpc_frame("chat.send", {"message": "Analyze the iris dataset"}))

            # Receive immediate RPC response with sessionId
            res = ws.receive_json()
            assert res["type"] == "res"
            assert res["ok"] is True
            assert "sessionId" in res["payload"]
            assert "runId" in res["payload"]

            # Receive stream.done event (agent background task completes)
            done = _recv_until(
                ws,
                lambda d: d.get("type") == "event" and d.get("event") == "stream.done",
            )
            assert done["payload"]["content"] == "Test analysis complete."

    def test_chat_history_after_send(
        self, client: TestClient, app: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """chat.history should return messages after an agent turn."""
        from ds_agent.domain.entities.messages import ChatMessage, Role

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Done.")
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.0
        mock_agent._callbacks = None

        async def _run_and_persist(message: str) -> str:
            app.state.app_state.transcript_store.replace_messages(
                "e2e-test",
                [
                    ChatMessage(role=Role.USER, content=message),
                    ChatMessage(role=Role.ASSISTANT, content="Hi there"),
                ],
            )
            return "Done."

        mock_agent.run = AsyncMock(side_effect=_run_and_persist)

        def _fake_create_agent(
            session_id, callbacks, model=None, *, authority_mode=None, **kwargs
        ):
            return mock_agent

        monkeypatch.setattr(
            app.state.app_state._sessions,
            "_create_agent",
            _fake_create_agent,
        )

        with client.websocket_connect("/ws") as ws:
            # Start a chat
            ws.send_json(_rpc_frame("chat.send", {"message": "Hello", "sessionId": "e2e-test"}))
            res = ws.receive_json()
            session_id = res["payload"]["sessionId"]
            run_id = res["payload"]["runId"]

            # Wait for done
            _recv_until(
                ws,
                lambda d: d.get("type") == "event" and d.get("event") == "stream.done",
            )

            ws.send_json(_rpc_frame("run.wait", {"runId": run_id, "timeoutMs": 1000}))
            run_res = _recv_until(ws, lambda d: d.get("type") == "res")
            assert run_res["ok"] is True
            assert run_res["payload"]["status"] == "succeeded"

            # Get history
            ws.send_json(_rpc_frame("chat.history", {"sessionId": session_id}))
            history_res = ws.receive_json()
            assert history_res["ok"] is True
            messages = history_res["payload"]["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "user"


# ---------------------------------------------------------------------------
# E2E Test: status RPC
# ---------------------------------------------------------------------------


class TestStatusRpcE2E:
    """status.get via WebSocket."""

    def test_status_get(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(_rpc_frame("status.get"))
            res = ws.receive_json()
            assert res["ok"] is True
            payload = res["payload"]
            assert "model" in payload
            assert "qualityPreset" in payload
            assert "mode" in payload
            assert "activeSessions" in payload
            assert "activeRuns" in payload


class TestProviderRpcE2E:
    """Provider status RPC round-trips."""

    def test_provider_health(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        import ds_agent.runtime.provider_factory as provider_factory

        provider_snapshot = [
            {
                "id": "ollama",
                "label": "Ollama",
                "status": "ok",
                "hasCredentials": True,
                "authStatus": "local",
                "latencyMs": 42,
                "message": "Ollama is reachable with 1 local model(s).",
                "checkedAt": 1_713_052_800,
                "modelCount": 1,
            }
        ]
        monkeypatch.setattr(
            provider_factory,
            "get_provider_health_snapshot",
            AsyncMock(return_value=provider_snapshot),
        )

        with client.websocket_connect("/ws") as ws:
            ws.send_json(_rpc_frame("provider.health"))
            res = ws.receive_json()

        assert res["ok"] is True
        assert res["payload"]["providers"] == provider_snapshot


# ---------------------------------------------------------------------------
# E2E Test: unknown method
# ---------------------------------------------------------------------------


class TestErrorHandlingE2E:
    """Error handling in WS RPC."""

    def test_unknown_method(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(_rpc_frame("nonexistent.method"))
            res = ws.receive_json()
            assert res["ok"] is False
            assert res["error"]["code"] == "UNKNOWN_METHOD"

    def test_invalid_type(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "not_req", "id": "x", "method": "status.get"})
            res = ws.receive_json()
            assert res["ok"] is False
