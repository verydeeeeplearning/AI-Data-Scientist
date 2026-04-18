"""Tests for team/admin RPC surfaces and runtime policy enforcement."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ds_agent.api.ws_handler import AppState, WsRpcHandler
from ds_agent.config.schema import AgentConfig, DSAgentConfig
from ds_agent.runtime.transcript_store import get_runtime_storage_root
from ds_agent.skills.hub import SkillHub

starlette = pytest.importorskip("starlette", reason="starlette not installed")
from starlette.websockets import WebSocketState  # noqa: E402


@pytest.fixture()
def app_state(tmp_path) -> AppState:
    config = DSAgentConfig(agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")))
    return AppState(config=config)


@pytest.fixture()
def mock_ws():
    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    ws.sent: list[dict] = []

    async def _send_json(data: dict) -> None:
        ws.sent.append(data)

    ws.send_json = AsyncMock(side_effect=_send_json)
    return ws


@pytest.fixture()
def rpc_handler(app_state: AppState, mock_ws) -> WsRpcHandler:
    return WsRpcHandler(state=app_state, websocket=mock_ws)


def _last_payload(mock_ws) -> dict:
    assert mock_ws.sent
    frame = mock_ws.sent[-1]
    assert frame["type"] == "res"
    assert frame["ok"] is True
    return frame["payload"]


class TestTeamEnterpriseRpc:
    @pytest.mark.asyncio
    async def test_org_get_returns_snapshot(self, rpc_handler: WsRpcHandler, mock_ws) -> None:
        await rpc_handler.handle_message({"type": "req", "id": "org-1", "method": "org.get"})

        payload = _last_payload(mock_ws)
        assert payload["organization"]["name"].endswith("Team")
        assert payload["organization"]["members"][0]["role"] == "admin"
        assert payload["usage"]["totalCostUsd"] == 0.0

    @pytest.mark.asyncio
    async def test_org_update_settings_can_clear_budget_caps(
        self,
        app_state: AppState,
        rpc_handler: WsRpcHandler,
        mock_ws,
    ) -> None:
        app_state.organization_store.update_settings(
            max_budget_usd_per_user=25.0,
            max_budget_usd_per_org=100.0,
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "org-clear",
                "method": "org.updateSettings",
                "params": {
                    "settings": {
                        "maxBudgetUsdPerUser": "",
                        "maxBudgetUsdPerOrg": "",
                    }
                },
            }
        )

        payload = _last_payload(mock_ws)
        settings = payload["organization"]["settings"]
        assert settings["maxBudgetUsdPerUser"] is None
        assert settings["maxBudgetUsdPerOrg"] is None

    @pytest.mark.asyncio
    async def test_org_audit_log_export_returns_csv(
        self,
        app_state: AppState,
        rpc_handler: WsRpcHandler,
        mock_ws,
    ) -> None:
        audit_path = (
            get_runtime_storage_root(app_state.config.agent.workspace_dir)
            / "audit_log.jsonl"
        )
        audit_path.write_text(
            json.dumps(
                {
                    "event": "post_tool_use",
                    "tool": "generate_report",
                    "timestamp": 1_713_052_800.0,
                    "session_id": "session-1",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "audit-1",
                "method": "org.auditLogExport",
                "params": {
                    "startDate": "2024-04-13",
                    "endDate": "2024-04-15",
                    "format": "csv",
                },
            }
        )

        payload = _last_payload(mock_ws)
        assert payload["recordCount"] == 1
        assert payload["contentType"] == "text/csv"
        assert "generate_report" in payload["content"]

    @pytest.mark.asyncio
    async def test_skill_get_returns_custom_skill(
        self,
        app_state: AppState,
        rpc_handler: WsRpcHandler,
        mock_ws,
        tmp_path,
    ) -> None:
        custom_dir = tmp_path / "skills" / "custom"
        app_state._skill_hub = SkillHub.from_directories([custom_dir])
        app_state.save_custom_skill(
            name="market-brief",
            description="Summarize market updates with safe web access.",
            content="# Market Brief\n\nUse concise bullet points.",
            tools=["web_search"],
            permissions={"network": ["docs.example.com"], "filesystem": ["workspace"]},
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "skill-1",
                "method": "skill.get",
                "params": {"name": "market-brief"},
            }
        )

        payload = _last_payload(mock_ws)
        assert payload["skill"]["name"] == "market-brief"
        assert "Use concise bullet points." in payload["skill"]["content"]
        assert payload["skill"]["permissions"]["network"] == ["docs.example.com"]

    @pytest.mark.asyncio
    async def test_skill_import_url_fetches_remote_markdown(
        self,
        rpc_handler: WsRpcHandler,
        mock_ws,
    ) -> None:
        remote_markdown = (
            "---\n"
            "name: remote-skill\n"
            "description: Imported from URL\n"
            "category: custom\n"
            "tags: [remote]\n"
            "tools: [execute_code]\n"
            "permissions:\n"
            "  network: []\n"
            "  filesystem: [workspace]\n"
            "enabled: true\n"
            "---\n"
            "# Remote Skill\n\n"
            "Use this from a hosted markdown file.\n"
        )
        with patch(
            "ds_agent.api.ws_handler._fetch_remote_skill_markdown",
            return_value=remote_markdown,
        ):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "skill-url-1",
                    "method": "skill.importUrl",
                    "params": {"url": "https://example.com/remote-skill.md"},
                }
            )

        payload = _last_payload(mock_ws)
        assert payload["skill"]["name"] == "remote-skill"
        assert payload["skill"]["sourceKind"] == "custom"


class TestTeamEnterpriseRuntime:
    @pytest.mark.asyncio
    async def test_start_run_blocks_remote_provider_when_external_transfer_disabled(
        self,
        app_state: AppState,
    ) -> None:
        app_state.organization_store.update_settings(external_data_transfer_allowed=False)

        with pytest.raises(
            ValueError,
            match=(
                r"External AI service data transfer is disabled by organization policy\."
            ),
        ):
            await app_state.start_run(
                session_id="session-1",
                message="Analyze this dataset",
                callbacks=MagicMock(),
            )
