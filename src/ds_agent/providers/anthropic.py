"""Anthropic native API provider.

Supports Extended Thinking, Prompt Caching, native tool use, and streaming.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog

from ds_agent.domain.entities.messages import (
    ChatMessage,
    LLMResponse,
    Role,
    ToolCall,
    Usage,
)
from ds_agent.domain.entities.provider_models import ModelInfo, ProviderSDKConfig

logger = structlog.get_logger()

ANTHROPIC_MODELS: dict[str, dict] = {
    # Current (April 2026)
    "claude-opus-4-6": {
        "display_name": "Claude Opus 4.6",
        "max_context": 1_000_000,
        "max_output": 128_000,
        "thinking": True,
        "caching": True,
        "vision": True,
    },
    "claude-sonnet-4-6": {
        "display_name": "Claude Sonnet 4.6",
        "max_context": 1_000_000,
        "max_output": 64_000,
        "thinking": True,
        "caching": True,
        "vision": True,
    },
    "claude-haiku-4-5": {
        "display_name": "Claude Haiku 4.5",
        "max_context": 200_000,
        "max_output": 64_000,
        "thinking": False,
        "caching": True,
        "vision": True,
    },
    # Legacy (still available)
    "claude-opus-4": {
        "display_name": "Claude Opus 4 (Legacy)",
        "max_context": 200_000,
        "max_output": 32_000,
        "thinking": True,
        "caching": True,
        "vision": True,
        "legacy": True,
    },
    "claude-sonnet-4": {
        "display_name": "Claude Sonnet 4 (Legacy)",
        "max_context": 200_000,
        "max_output": 16_000,
        "thinking": True,
        "caching": True,
        "vision": True,
        "legacy": True,
    },
    "claude-haiku-3.5": {
        "display_name": "Claude 3.5 Haiku (Legacy)",
        "max_context": 200_000,
        "max_output": 8_192,
        "thinking": False,
        "caching": True,
        "vision": True,
        "legacy": True,
    },
}


class AnthropicProvider:
    """Anthropic native API provider."""

    def __init__(self, model: str, config: ProviderSDKConfig | None = None) -> None:
        self._model = self._normalize_model_id(model)
        self._config = config or ProviderSDKConfig()

        try:
            import anthropic

            self._client = anthropic.AsyncAnthropic(
                api_key=self._config.api_key or None,
                base_url=self._config.base_url,
                timeout=self._config.timeout,
                max_retries=self._config.max_retries,
            )
        except ImportError as e:
            raise ImportError("anthropic SDK is required. Install: pip install anthropic") from e

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        """Anthropic Messages API call.

        When *on_delta* is provided and thinking mode is off, the response is
        streamed — each text token is delivered to *on_delta* as it arrives,
        and the full assembled ``LLMResponse`` is returned at the end.
        """
        system_prompt, api_messages = self._split_system_message(messages)

        call_kwargs: dict = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": max_tokens or self._get_default_max_tokens(),
        }
        if system_prompt:
            call_kwargs["system"] = system_prompt
        if tools:
            call_kwargs["tools"] = self._convert_tools_to_anthropic(tools)
        model_meta = self._get_model_meta()
        thinking_enabled = model_meta.get("thinking") and kwargs.get("thinking", True)

        if thinking_enabled:
            # 4.10 fix: Anthropic API requires temperature=1 when thinking is enabled.
            # Setting temperature=0 with thinking raises an API validation error.
            call_kwargs["temperature"] = 1
            call_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": kwargs.get("thinking_budget", 10000),
            }
        elif temperature > 0:
            call_kwargs["temperature"] = temperature

        # 4.2 fix: Stream text deltas when on_delta callback is provided.
        # Streaming is skipped when thinking is enabled (thinking blocks need
        # special handling; streaming still works but adds complexity for no UX
        # gain since thinking text isn't shown to users via on_delta).
        if on_delta is not None and not thinking_enabled:
            async with self._client.messages.stream(**call_kwargs) as stream:
                async for text in stream.text_stream:
                    await on_delta(text)
                raw_response = await stream.get_final_message()
        else:
            raw_response = await self._client.messages.create(**call_kwargs)

        return self._convert_response(raw_response)

    async def count_tokens(self, messages: list[ChatMessage]) -> int:
        """Anthropic token counting API."""
        system_prompt, api_messages = self._split_system_message(messages)
        try:
            result = await self._client.messages.count_tokens(
                model=self._model,
                messages=api_messages,
                system=system_prompt or "",
            )
            return int(result.input_tokens)
        except Exception:
            total = sum(len(m.content or "") for m in messages)
            return total // 4

    def get_model_info(self) -> ModelInfo:
        """Anthropic model metadata."""
        meta = self._get_model_meta()
        pricing = {
            "claude-opus-4-6": (5.0, 25.0),
            "claude-sonnet-4-6": (3.0, 15.0),
            "claude-haiku-4-5": (1.0, 5.0),
            "claude-opus-4": (15.0, 75.0),
            "claude-sonnet-4": (3.0, 15.0),
            "claude-haiku-3.5": (0.8, 4.0),
        }
        costs = pricing.get(self._model, (3.0, 15.0))

        return ModelInfo(
            model_id=self._model,
            provider="anthropic",
            display_name=meta.get("display_name", self._model),
            max_context_tokens=meta.get("max_context", 200_000),
            max_output_tokens=meta.get("max_output", 8_192),
            supports_tools=True,
            supports_vision=meta.get("vision", False),
            supports_thinking=meta.get("thinking", False),
            supports_caching=meta.get("caching", False),
            input_cost_per_mtok=costs[0],
            output_cost_per_mtok=costs[1],
        )

    # --- Private helpers ---

    def _normalize_model_id(self, model: str) -> str:
        if model.startswith("anthropic/"):
            return model[len("anthropic/") :]
        return model

    def _get_model_meta(self) -> dict:
        if self._model in ANTHROPIC_MODELS:
            return ANTHROPIC_MODELS[self._model]
        for key, meta in ANTHROPIC_MODELS.items():
            if self._model.startswith(key):
                return meta
        return {"max_context": 200_000, "max_output": 8_192}

    def _get_default_max_tokens(self) -> int:
        return int(self._get_model_meta().get("max_output", 8_192))

    def _split_system_message(self, messages: list[ChatMessage]) -> tuple[str | None, list[dict]]:
        """Separate system messages into Anthropic system parameter."""
        system_parts: list[str] = []
        api_messages: list[dict] = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                if msg.content:
                    system_parts.append(msg.content)
                continue

            anthropic_msg = self._convert_message(msg)
            if anthropic_msg:
                api_messages.append(anthropic_msg)

        system_prompt = "\n\n".join(system_parts) if system_parts else None
        return system_prompt, api_messages

    def _convert_message(self, msg: ChatMessage) -> dict | None:
        """ChatMessage -> Anthropic API message format."""
        if msg.role == Role.ASSISTANT:
            d: dict = {"role": "assistant"}
            content_blocks: list[dict] = []
            if msg.content:
                content_blocks.append({"type": "text", "text": msg.content})
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
            d["content"] = content_blocks or msg.content or ""
            return d

        if msg.role == Role.USER:
            return {"role": "user", "content": msg.content or ""}

        if msg.role == Role.TOOL:
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content or "",
                    }
                ],
            }

        return None

    def _convert_tools_to_anthropic(self, openai_tools: list[dict]) -> list[dict]:
        """OpenAI function calling schema -> Anthropic tool schema."""
        anthropic_tools = []
        for tool in openai_tools:
            func = tool.get("function", tool)
            anthropic_tools.append(
                {
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return anthropic_tools

    def _convert_response(self, raw_response: object) -> LLMResponse:
        """Anthropic response -> LLMResponse."""
        content_text: str | None = None
        thinking_text: str | None = None
        tool_calls: list[ToolCall] = []

        for block in raw_response.content:  # type: ignore[attr-defined]
            if block.type == "text":
                content_text = block.text
            elif block.type == "thinking":
                thinking_text = block.thinking
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))

        raw_usage = raw_response.usage  # type: ignore[attr-defined]
        usage = Usage(
            input_tokens=raw_usage.input_tokens,
            output_tokens=raw_usage.output_tokens,
            cache_read_tokens=getattr(raw_usage, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(raw_usage, "cache_creation_input_tokens", 0) or 0,
        )

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls or None,
            usage=usage,
            model=raw_response.model,  # type: ignore[attr-defined]
            stop_reason=raw_response.stop_reason,  # type: ignore[attr-defined]
            thinking=thinking_text,
        )
