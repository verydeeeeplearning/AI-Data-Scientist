"""Core domain entities for LLM messaging."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    """LLM이 요청한 도구 호출."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """도구 실행 결과."""

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class ChatMessage:
    """통합 메시지 포맷. 모든 프로바이더가 이 포맷으로 변환."""

    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    cache_control: dict[str, str] | None = None


@dataclass
class Usage:
    """LLM API 사용량."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.reasoning_tokens


@dataclass
class LLMResponse:
    """LLM API 응답 통합 포맷."""

    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    stop_reason: str | None = None
    thinking: str | None = None
