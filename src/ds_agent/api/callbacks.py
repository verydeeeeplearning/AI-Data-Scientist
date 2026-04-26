"""WebSocket-based AgentCallbacks — emits events to connected Electron client."""

from __future__ import annotations

import asyncio
import time

import structlog
from starlette.websockets import WebSocket, WebSocketState

from ds_agent.api.event_envelope import ENVELOPE_VERSION, wrap_event
from ds_agent.application.learning.harness_warning_ingestor import HarnessWarningIngestor
from ds_agent.domain.value_objects.budget import BudgetThresholdEvent
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore

logger = structlog.get_logger()

_MAX_RESULT_PREVIEW = 2000


class WsAgentCallbacks:
    """Agent callbacks that push events over a WebSocket connection.

    Implements the AgentCallbacks protocol defined in
    ``ds_agent.domain.interfaces.llm_provider``.
    """

    def __init__(
        self,
        websocket: WebSocket,
        *,
        workspace_dir: str | None = None,
        warning_ingestor: HarnessWarningIngestor | None = None,
    ) -> None:
        self._ws = websocket
        self._background_tasks: set[asyncio.Task] = set()  # type: ignore[type-arg]
        self._tool_start_times: dict[str, float] = {}
        self._warning_ingestor = warning_ingestor
        if self._warning_ingestor is None and workspace_dir is not None:
            self._warning_ingestor = HarnessWarningIngestor(
                SqliteLearningStore.for_workspace(workspace_dir)
            )
        self._current_session_id: str | None = None
        self._current_run_id: str | None = None
        self._surface = "ws"

    async def close(self) -> None:
        """CON-05: Cancel and await all pending background tasks on disconnect."""
        for task in list(self._background_tasks):
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()

    # -- Sync emit for HookContext ------------------------------------------------

    def emit_event(self, event: str, payload: dict) -> None:
        """Sync fire-and-forget emit for use as HookContext.emit callback.

        Schedules the async WebSocket send on the running event loop.
        """
        self._remember_runtime_context(payload)
        self._ingest_warning_if_needed(event, payload)
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self._emit(event, payload))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        except RuntimeError:
            logger.debug("emit_event_no_loop", event=event)

    # -- AgentCallbacks protocol ------------------------------------------------

    async def on_tool_start(self, tool_name: str, arguments: dict) -> None:
        self._tool_start_times[tool_name] = time.monotonic()
        await self._emit("tool.start", {"name": tool_name, "args": arguments})

    async def on_tool_end(self, tool_name: str, result: str, is_error: bool) -> None:
        start = self._tool_start_times.pop(tool_name, time.monotonic())
        elapsed_ms = round((time.monotonic() - start) * 1000)
        await self._emit(
            "tool.end",
            {
                "name": tool_name,
                "result": result[:_MAX_RESULT_PREVIEW],
                "success": not is_error,
                "elapsed": elapsed_ms,
            },
        )

    async def on_thinking(self, thinking_text: str) -> None:
        await self._emit("thinking", {"text": thinking_text})

    async def on_stream_delta(self, delta: str) -> None:
        await self._emit("stream.delta", {"token": delta})

    async def on_step(self, step_num: int, message: str) -> None:
        await self._emit("status.update", {"step": step_num, "message": message})

    async def on_status(self, status: str, detail: str) -> None:
        await self._emit("status.update", {"status": status, "detail": detail})

    async def on_budget_warning(self, event: BudgetThresholdEvent) -> None:
        await self._emit(
            "budget.warning",
            {
                "dimension": event.dimension,
                "level": event.level,
                "pct": event.pct,
                "message": event.message,
            },
        )

    # -- Helpers ----------------------------------------------------------------

    async def emit_stream_done(
        self,
        content: str,
        cost: float,
        message_id: str | None = None,
        cards: list[dict[str, object]] | None = None,
    ) -> None:
        """Emit final stream.done event after agent completes."""
        payload: dict[str, object] = {"content": content, "cost": cost}
        if message_id:
            payload["messageId"] = message_id
        if cards:
            payload["cards"] = cards
        await self._emit("stream.done", payload)

    async def emit_stream_error(
        self,
        message: str,
        *,
        code: str | None = None,
        message_id: str | None = None,
    ) -> None:
        """Emit a terminal stream.error event after a failed agent turn."""
        payload: dict[str, object] = {"message": message}
        if code:
            payload["code"] = code
        if message_id:
            payload["messageId"] = message_id
        await self._emit("stream.error", payload)

    async def emit_file_created(self, path: str, file_type: str, size: int) -> None:
        """Emit file.created event when agent produces an artifact."""
        await self._emit("file.created", {"path": path, "type": file_type, "size": size})

    async def _emit(
        self,
        event: str,
        payload: dict,
        *,
        source: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Send a WsEvent frame to the client.

        Frame is envelope-versioned per cross_cutting/PLAN_03 (ADR-0007). The
        outer ``type:"event"`` discriminator stays for RPC-vs-event routing on
        the wire; the envelope fields (version, ts, source, correlationId) are
        inlined alongside it for backward compatibility with the existing
        renderer message handler.
        """
        if self._ws.client_state != WebSocketState.CONNECTED:
            return
        envelope = wrap_event(event, payload, source=source, correlation_id=correlation_id)
        frame: dict[str, object] = {
            "type": "event",
            "event": event,
            "version": envelope.version,
            "payload": payload,
            "ts": envelope.ts,
        }
        if envelope.source is not None:
            frame["source"] = envelope.source
        if envelope.correlation_id is not None:
            frame["correlationId"] = envelope.correlation_id
        try:
            await self._ws.send_json(frame)
        except Exception as e:
            logger.warning("ws_emit_failed", event=event, error=str(e))

    @staticmethod
    def envelope_version() -> str:
        """Expose current envelope version for handshake responses."""
        return ENVELOPE_VERSION

    def _remember_runtime_context(self, payload: dict) -> None:
        session_id = payload.get("sessionId")
        run_id = payload.get("runId")
        if isinstance(session_id, str) and session_id.strip():
            self._current_session_id = session_id
        if isinstance(run_id, str) and run_id.strip():
            self._current_run_id = run_id
        surface = payload.get("surface")
        if isinstance(surface, str) and surface.strip():
            self._surface = surface

    def _ingest_warning_if_needed(self, event: str, payload: dict) -> None:
        if event != "harness.warning" or self._warning_ingestor is None:
            return
        try:
            self._warning_ingestor.ingest(
                payload,
                session_id=_first_non_empty_string(
                    payload.get("sessionId"),
                    self._current_session_id,
                ),
                run_id=_first_non_empty_string(payload.get("runId"), self._current_run_id),
                surface=_first_non_empty_string(payload.get("surface"), self._surface) or "ws",
            )
        except Exception as exc:
            logger.warning("harness_warning_ingest_failed", error=str(exc))


def _first_non_empty_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return None
