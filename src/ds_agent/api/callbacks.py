"""WebSocket-based AgentCallbacks — emits events to connected Electron client."""

from __future__ import annotations

import asyncio
import time

import structlog
from starlette.websockets import WebSocket, WebSocketState

from ds_agent.api.event_envelope import ENVELOPE_VERSION, wrap_event
from ds_agent.domain.value_objects.budget import BudgetThresholdEvent

logger = structlog.get_logger()

_MAX_RESULT_PREVIEW = 2000


class WsAgentCallbacks:
    """Agent callbacks that push events over a WebSocket connection.

    Implements the AgentCallbacks protocol defined in
    ``ds_agent.domain.interfaces.llm_provider``.
    """

    def __init__(self, websocket: WebSocket) -> None:
        self._ws = websocket
        self._background_tasks: set[asyncio.Task] = set()  # type: ignore[type-arg]
        self._tool_start_times: dict[str, float] = {}

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

    async def emit_stream_done(self, content: str, cost: float) -> None:
        """Emit final stream.done event after agent completes."""
        await self._emit("stream.done", {"content": content, "cost": cost})

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
