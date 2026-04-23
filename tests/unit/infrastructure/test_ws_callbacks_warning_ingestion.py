from __future__ import annotations

import asyncio

from starlette.websockets import WebSocketState

from ds_agent.api.callbacks import WsAgentCallbacks
from ds_agent.domain.learning.learning_item import LearningItemType
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore


class _FakeWebSocket:
    def __init__(self) -> None:
        self.client_state = WebSocketState.CONNECTED
        self.sent: list[dict[str, object]] = []

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)


async def test_emit_event_ingests_harness_warning_into_learning_store(tmp_path) -> None:
    ws = _FakeWebSocket()
    callbacks = WsAgentCallbacks(ws, workspace_dir=str(tmp_path))

    callbacks.emit_event(
        "task.started",
        {
            "sessionId": "session-1",
            "runId": "run-1",
            "surface": "ws",
            "message": "Profile the data.",
        },
    )
    callbacks.emit_event(
        "harness.warning",
        {
            "type": "leakage",
            "message": "Potential target leakage detected.",
            "severity": "high",
        },
    )
    await asyncio.sleep(0.05)

    store = SqliteLearningStore.for_workspace(str(tmp_path))
    items = store.list_items(item_type=LearningItemType.PATTERN)
    assert len(items) == 1
    assert items[0].metadata["sessionId"] == "session-1"
    assert items[0].metadata["runId"] == "run-1"
    assert items[0].metadata["warningType"] == "leakage"
    assert any(frame.get("event") == "harness.warning" for frame in ws.sent)
