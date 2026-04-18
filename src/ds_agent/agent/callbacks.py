"""Agent callback implementations."""

from __future__ import annotations

from ds_agent.domain.interfaces.llm_provider import AgentCallbacks
from ds_agent.domain.value_objects.budget import BudgetThresholdEvent


class NullCallbacks(AgentCallbacks):  # type: ignore[misc]
    """Default no-op callbacks. Used when no callbacks are provided."""

    def emit_event(self, event: str, payload: dict) -> None:
        """Sync fire-and-forget event emission. No-op for null callbacks."""

    async def on_tool_start(self, tool_name: str, arguments: dict) -> None:
        pass

    async def on_tool_end(self, tool_name: str, result: str, is_error: bool) -> None:
        pass

    async def on_thinking(self, thinking_text: str) -> None:
        pass

    async def on_stream_delta(self, delta: str) -> None:
        pass

    async def on_step(self, step_num: int, message: str) -> None:
        pass

    async def on_status(self, status: str, detail: str) -> None:
        pass

    async def on_budget_warning(self, event: BudgetThresholdEvent) -> None:
        pass
