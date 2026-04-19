"""Verify WS emit frames are envelope-versioned (PLAN_03 §5.1)."""

from __future__ import annotations

from typing import Any

import pytest

from ds_agent.api.callbacks import WsAgentCallbacks
from ds_agent.api.event_envelope import ENVELOPE_VERSION


class _FakeWs:
    """Minimal stand-in for starlette.WebSocket capturing send_json calls."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.client_state = _ConnectedState()

    async def send_json(self, frame: dict[str, Any]) -> None:
        self.sent.append(frame)


class _ConnectedState:
    """Mimics ``WebSocketState.CONNECTED`` value-equality."""

    name = "CONNECTED"

    def __eq__(self, other: object) -> bool:
        # Tests compare client_state == WebSocketState.CONNECTED. Make this
        # truthy by checking name equality.
        return getattr(other, "name", None) == "CONNECTED"

    def __hash__(self) -> int:
        return hash(self.name)


@pytest.mark.asyncio
async def test_emit_includes_envelope_version() -> None:
    ws = _FakeWs()
    callbacks = WsAgentCallbacks(ws)  # type: ignore[arg-type]
    await callbacks._emit("mission.context.updated", {"goal": "x"})
    assert len(ws.sent) == 1
    frame = ws.sent[0]
    assert frame["type"] == "event"
    assert frame["event"] == "mission.context.updated"
    assert frame["version"] == ENVELOPE_VERSION
    assert frame["payload"] == {"goal": "x"}
    assert isinstance(frame["ts"], float)
    assert "source" not in frame
    assert "correlationId" not in frame


@pytest.mark.asyncio
async def test_emit_includes_optional_envelope_fields_when_provided() -> None:
    ws = _FakeWs()
    callbacks = WsAgentCallbacks(ws)  # type: ignore[arg-type]
    await callbacks._emit(
        "card.created",
        {"id": "c-1"},
        source="agent-runner",
        correlation_id="req-99",
    )
    frame = ws.sent[0]
    assert frame["source"] == "agent-runner"
    assert frame["correlationId"] == "req-99"


@pytest.mark.asyncio
async def test_emit_skips_when_websocket_not_connected() -> None:
    ws = _FakeWs()
    ws.client_state = type("Disconnected", (), {"name": "DISCONNECTED"})()  # type: ignore[assignment]
    callbacks = WsAgentCallbacks(ws)  # type: ignore[arg-type]
    await callbacks._emit("x", {})
    assert ws.sent == []


def test_envelope_version_classmethod_exposes_current_version() -> None:
    assert WsAgentCallbacks.envelope_version() == ENVELOPE_VERSION
