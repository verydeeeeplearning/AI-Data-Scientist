"""Task-local runtime context for tool execution."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

_current_tool_runtime_context: ContextVar[ToolRuntimeContext | None] = ContextVar(
    "tool_runtime_context",
    default=None,
)


@dataclass(slots=True)
class ToolRuntimeContext:
    """Task-local metadata available to tools during dispatch."""

    session_id: str | None
    run_id: str | None
    surface: str
    emit_event: Callable[[str, dict], None] | None = None
    approval_store: Any | None = None
    skill_hub: Any | None = None


def set_tool_runtime_context(context: ToolRuntimeContext) -> Token[ToolRuntimeContext | None]:
    """Set the current task-local tool runtime context."""
    return _current_tool_runtime_context.set(context)


def reset_tool_runtime_context(token: Token[ToolRuntimeContext | None]) -> None:
    """Restore the previous task-local tool runtime context."""
    _current_tool_runtime_context.reset(token)


def get_tool_runtime_context() -> ToolRuntimeContext | None:
    """Return the current task-local tool runtime context."""
    return _current_tool_runtime_context.get()
