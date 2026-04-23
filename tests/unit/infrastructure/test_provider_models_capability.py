"""Round-trip tests for provider.models RPC capability metadata.

W1-C PLAN_06: ensures the ``provider.models`` WebSocket RPC enriches every
catalog entry with curated capability metadata so the renderer can stop
relying on its heuristic profiling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from starlette.websockets import WebSocketState

from ds_agent.api.ws_handler import AppState, WsRpcHandler
from ds_agent.config.schema import AgentConfig, DSAgentConfig
from ds_agent.providers.model_metadata import (
    CAPABILITY_BADGES,
    CAPABILITY_GROUPS,
)


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
def rpc_handler(tmp_path, mock_ws):
    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
    )
    return WsRpcHandler(state=AppState(config=config), websocket=mock_ws)


class TestProviderModelsCapabilityEnrichment:
    async def test_every_catalog_entry_carries_capability_fields(
        self, rpc_handler, mock_ws
    ):
        await rpc_handler.handle_message(
            {"type": "req", "id": "pm-cap-1", "method": "provider.models"}
        )
        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        models = frame["payload"]["models"]
        assert models, "catalog must not be empty"

        for entry in models:
            assert "capabilityGroup" in entry, f"missing capabilityGroup on {entry['id']}"
            assert "capabilityBadges" in entry, f"missing capabilityBadges on {entry['id']}"
            assert "recommendedFor" in entry, f"missing recommendedFor on {entry['id']}"
            assert "providerLabelLegacy" in entry, (
                f"missing providerLabelLegacy on {entry['id']}"
            )
            assert entry["capabilityGroup"] in CAPABILITY_GROUPS
            assert isinstance(entry["capabilityBadges"], list)
            assert isinstance(entry["recommendedFor"], list)
            assert len(entry["capabilityBadges"]) >= 1
            for badge in entry["capabilityBadges"]:
                assert badge in CAPABILITY_BADGES, (
                    f"invalid badge {badge} on {entry['id']}"
                )

    async def test_curated_anthropic_opus_uses_best_quality(
        self, rpc_handler, mock_ws
    ):
        await rpc_handler.handle_message(
            {"type": "req", "id": "pm-cap-2", "method": "provider.models"}
        )
        models = mock_ws.sent[0]["payload"]["models"]
        opus = next((m for m in models if m["id"] == "anthropic/claude-opus-4-6"), None)
        assert opus is not None
        assert opus["capabilityGroup"] == "best_quality"
        assert "strong_reasoning" in opus["capabilityBadges"]

    async def test_legacy_id_remains_stable(self, rpc_handler, mock_ws):
        # Stored model ids must not change so user localStorage selections survive.
        await rpc_handler.handle_message(
            {"type": "req", "id": "pm-cap-3", "method": "provider.models"}
        )
        models = mock_ws.sent[0]["payload"]["models"]
        ids = {m["id"] for m in models}
        for required in (
            "anthropic/claude-opus-4-6",
            "anthropic/claude-sonnet-4-6",
            "openai/gpt-5.4",
            "codex/gpt-5.4",
            "gemini/gemini-2.5-pro",
            "deepseek/deepseek-chat",
            "groq/llama-4-scout-17b-16e-instruct",
        ):
            assert required in ids, f"stable model id {required} disappeared"

    async def test_provider_label_legacy_includes_old_provider_naming(
        self, rpc_handler, mock_ws
    ):
        await rpc_handler.handle_message(
            {"type": "req", "id": "pm-cap-4", "method": "provider.models"}
        )
        models = mock_ws.sent[0]["payload"]["models"]
        sample = next(m for m in models if m["id"] == "anthropic/claude-sonnet-4-6")
        legacy_label = sample["providerLabelLegacy"]
        assert legacy_label is not None
        assert "anthropic" in legacy_label.lower()
        assert "claude-sonnet-4-6" in legacy_label
