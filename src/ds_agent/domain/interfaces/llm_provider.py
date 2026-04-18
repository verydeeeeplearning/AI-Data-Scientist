"""LLM Provider port interface (Domain layer)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.messages import ChatMessage, LLMResponse
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.domain.value_objects.budget import BudgetThresholdEvent


@runtime_checkable
class LLMProvider(Protocol):
    """LLM 프로바이더 포트 인터페이스.

    Application 레이어가 의존하는 추상화.
    Infrastructure 레이어가 구현.
    """

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
        **kwargs: object,
    ) -> LLMResponse: ...

    async def count_tokens(self, messages: list[ChatMessage]) -> int: ...

    def get_model_info(self) -> ModelInfo: ...


@runtime_checkable
class AgentCallbacks(Protocol):
    """에이전트 이벤트 콜백 포트."""

    async def on_tool_start(self, tool_name: str, arguments: dict) -> None: ...
    async def on_tool_end(self, tool_name: str, result: str, is_error: bool) -> None: ...
    async def on_thinking(self, thinking_text: str) -> None: ...
    async def on_stream_delta(self, delta: str) -> None: ...
    async def on_step(self, step_num: int, message: str) -> None: ...
    async def on_status(self, status: str, detail: str) -> None: ...
    async def on_budget_warning(self, event: BudgetThresholdEvent) -> None: ...
