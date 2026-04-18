"""Provider base utilities and re-exports."""

from __future__ import annotations

import json
from typing import Any

from ds_agent.domain.entities.messages import (
    ChatMessage,
    LLMResponse,
    Role,
    ToolCall,
    Usage,
)
from ds_agent.domain.entities.provider_models import ModelInfo, ProviderSDKConfig
from ds_agent.domain.interfaces.llm_provider import LLMProvider

__all__ = [
    "ChatMessage",
    "LLMProvider",
    "LLMResponse",
    "ModelInfo",
    "ProviderSDKConfig",
    "Role",
    "ToolCall",
    "Usage",
    "messages_to_openai_format",
    "messages_to_responses_input",
    "openai_response_to_llm_response",
    "openai_tools_to_responses_format",
    "responses_response_to_llm_response",
]


def messages_to_openai_format(messages: list[ChatMessage]) -> list[dict]:
    """ChatMessage list -> OpenAI API format dicts."""
    result = []
    for msg in messages:
        d: dict = {"role": msg.role.value, "content": msg.content or ""}
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in msg.tool_calls
            ]
            d.pop("content", None)
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        if msg.name:
            d["name"] = msg.name
        result.append(d)
    return result


def messages_to_responses_input(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """ChatMessage list -> Responses API input items."""
    result: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role in {Role.SYSTEM, Role.USER}:
            result.append(
                {
                    "type": "message",
                    "role": msg.role.value,
                    "content": [{"type": "input_text", "text": msg.content or ""}],
                }
            )
            continue

        if msg.role == Role.ASSISTANT:
            if msg.content:
                result.append(
                    {
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": msg.content,
                                "annotations": [],
                            }
                        ],
                    }
                )

            for tc in msg.tool_calls or []:
                result.append(
                    {
                        "type": "function_call",
                        "call_id": tc.id,
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    }
                )
            continue

        if msg.role == Role.TOOL:
            result.append(
                {
                    "type": "function_call_output",
                    "call_id": msg.tool_call_id or "",
                    "output": msg.content or "",
                }
            )

    return result


def openai_tools_to_responses_format(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chat Completions tool schema -> Responses API tool schema."""
    converted: list[dict[str, Any]] = []
    for tool in tools:
        function_spec = tool.get("function")
        if not isinstance(function_spec, dict):
            converted.append(dict(tool))
            continue

        next_tool: dict[str, Any] = {
            "type": tool.get("type", "function"),
            "name": function_spec["name"],
            "parameters": function_spec.get("parameters", {"type": "object", "properties": {}}),
        }
        if function_spec.get("description"):
            next_tool["description"] = function_spec["description"]
        if function_spec.get("strict") is not None:
            next_tool["strict"] = function_spec["strict"]
        elif tool.get("strict") is not None:
            next_tool["strict"] = tool["strict"]
        converted.append(next_tool)
    return converted


def _get_field(source: object, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _parse_tool_arguments(raw_arguments: object) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if raw_arguments is None:
        return {}
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
        except (json.JSONDecodeError, TypeError):
            return {"_raw": raw_arguments}
        return parsed if isinstance(parsed, dict) else {"_raw": raw_arguments}
    return {"_raw": raw_arguments}


def _response_content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for part in content:
        part_type = _get_field(part, "type", "")
        if part_type in {"input_text", "output_text"}:
            text = _get_field(part, "text", "")
            if isinstance(text, str):
                parts.append(text)
        elif part_type == "refusal":
            refusal = _get_field(part, "refusal", "")
            if isinstance(refusal, str):
                parts.append(refusal)
    return "".join(parts)


def _response_reasoning_to_text(item: object) -> str:
    summary = _get_field(item, "summary")
    if isinstance(summary, list):
        parts = []
        for part in summary:
            text = _get_field(part, "text", "")
            if isinstance(text, str) and text:
                parts.append(text)
        return "\n\n".join(parts)
    return ""


def _responses_usage_to_usage(raw_usage: object) -> Usage:
    input_tokens = int(_get_field(raw_usage, "input_tokens", 0) or 0)
    output_tokens = int(_get_field(raw_usage, "output_tokens", 0) or 0)
    input_details = _get_field(raw_usage, "input_tokens_details")
    cached_tokens = int(_get_field(input_details, "cached_tokens", 0) or 0)
    output_details = _get_field(raw_usage, "output_tokens_details")
    reasoning_tokens = int(
        _get_field(output_details, "reasoning_tokens", _get_field(raw_usage, "reasoning_tokens", 0))
        or 0
    )
    return Usage(
        input_tokens=max(0, input_tokens - cached_tokens),
        output_tokens=output_tokens,
        cache_read_tokens=cached_tokens,
        reasoning_tokens=reasoning_tokens,
    )


def _responses_status_to_stop_reason(status: object, has_tool_calls: bool) -> str:
    if has_tool_calls:
        return "tool_calls"
    if not isinstance(status, str):
        return "stop"
    if status in {"completed", "queued", "in_progress"}:
        return "stop"
    if status == "incomplete":
        return "length"
    if status in {"failed", "cancelled"}:
        return "error"
    return status


def openai_response_to_llm_response(raw_response: object) -> LLMResponse:
    """OpenAI/LiteLLM raw response -> LLMResponse."""
    choice = raw_response.choices[0]  # type: ignore[attr-defined]
    message = choice.message

    tool_calls = None
    if message.tool_calls:
        tool_calls = []
        for tc in message.tool_calls:
            tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=_parse_tool_arguments(tc.function.arguments),
                )
            )

    usage_data = raw_response.usage  # type: ignore[attr-defined]
    usage = Usage(
        input_tokens=getattr(usage_data, "prompt_tokens", 0),
        output_tokens=getattr(usage_data, "completion_tokens", 0),
        cache_read_tokens=getattr(usage_data, "cache_read_input_tokens", 0),
        reasoning_tokens=getattr(usage_data, "reasoning_tokens", 0) or 0,
    )

    return LLMResponse(
        content=message.content,
        tool_calls=tool_calls,
        usage=usage,
        model=raw_response.model or "",  # type: ignore[attr-defined]
        stop_reason=choice.finish_reason,
    )


def responses_response_to_llm_response(raw_response: object) -> LLMResponse:
    """Responses API raw response -> LLMResponse."""
    output = _get_field(raw_response, "output", []) or []
    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls: list[ToolCall] = []

    for item in output:
        item_type = _get_field(item, "type", "")
        if item_type == "message" and _get_field(item, "role", "") == "assistant":
            text = _response_content_to_text(_get_field(item, "content", []))
            if text:
                text_parts.append(text)
            continue

        if item_type == "function_call":
            tool_calls.append(
                ToolCall(
                    id=str(_get_field(item, "call_id", _get_field(item, "id", "")) or ""),
                    name=str(_get_field(item, "name", "") or ""),
                    arguments=_parse_tool_arguments(_get_field(item, "arguments")),
                )
            )
            continue

        if item_type == "reasoning":
            reasoning = _response_reasoning_to_text(item)
            if reasoning:
                reasoning_parts.append(reasoning)

    output_text = _get_field(raw_response, "output_text")
    content = output_text if isinstance(output_text, str) and output_text else None
    if content is None and text_parts:
        content = "".join(text_parts)

    return LLMResponse(
        content=content,
        tool_calls=tool_calls or None,
        usage=_responses_usage_to_usage(_get_field(raw_response, "usage")),
        model=str(_get_field(raw_response, "model", "") or ""),
        stop_reason=_responses_status_to_stop_reason(
            _get_field(raw_response, "status"),
            bool(tool_calls),
        ),
        thinking="\n\n".join(reasoning_parts) or None,
    )
