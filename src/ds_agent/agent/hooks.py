"""Tool Hook framework — PreToolUse / PostToolUse (Claude Code pattern).

Hooks run before and after tool execution, enabling:
- Permission enforcement (DENY)
- Argument modification (MODIFY)
- Audit logging
- Budget guards
- Learning triggers
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from ds_agent.application.services.verifier_orchestrator import VerifierOrchestrator
    from ds_agent.domain.entities.messages import ChatMessage
    from ds_agent.domain.entities.task_contract import TaskContract

logger = structlog.get_logger()

# Type alias for the emit callback: (event_name, payload) -> None
EmitFn = Callable[[str, dict[str, Any]], None]


def _noop_emit(event: str, payload: dict[str, Any]) -> None:
    """Default no-op emit when no WebSocket is wired."""


class HookAction(StrEnum):
    """Action a PreToolUse hook can return."""

    ALLOW = "allow"
    DENY = "deny"
    MODIFY = "modify"


@dataclass
class HookContext:
    """Context passed to every hook invocation."""

    mode: str = "auto"  # auto | supervised | step-by-step
    authority_mode: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    user_message: str | None = None
    iteration: int = 0
    total_cost_usd: float = 0.0
    user_approved: bool = False
    environment: str = "dev"
    approval_store: Any | None = None
    workspace_path: str | None = None
    active_task_contract: TaskContract | None = None
    verifier_orchestrator: VerifierOrchestrator | None = None
    recent_messages: tuple[ChatMessage, ...] = field(default_factory=tuple)
    emit: EmitFn = _noop_emit


@dataclass
class PreToolUseResult:
    """Result of a PreToolUse hook."""

    action: HookAction = HookAction.ALLOW
    modified_arguments: dict | None = None
    deny_reason: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class PostToolUseResult:
    """Result of a PostToolUse hook."""

    modified_result: str | None = None
    log_entry: dict | None = None
    trigger_learning: bool = False


@dataclass
class FinalResponseResult:
    """Result of a final-response hook."""

    modified_response: str | None = None
    requires_followup: bool = False
    followup_reason: str | None = None


class ToolHook:
    """Base class for tool hooks. Override pre/post methods as needed."""

    name: str = "base_hook"
    priority: int = 100  # lower = runs first

    async def on_session_init(self, context: HookContext) -> str | None:
        """Called once at session start. Return text to inject into context, or None."""
        return None

    async def pre_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        context: HookContext,
    ) -> PreToolUseResult:
        return PreToolUseResult()

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        return PostToolUseResult()

    async def on_final_response(
        self,
        response: str,
        context: HookContext,
    ) -> FinalResponseResult:
        """Called once when the assistant has produced its final response."""
        return FinalResponseResult()


class HookRegistry:
    """Registry of hooks, executed in priority order."""

    def __init__(self) -> None:
        self._hooks: list[ToolHook] = []

    def register(self, hook: ToolHook) -> None:
        self._hooks.append(hook)
        self._hooks.sort(key=lambda h: h.priority)

    @property
    def hooks(self) -> list[ToolHook]:
        return list(self._hooks)

    async def run_session_init(self, context: HookContext) -> list[str]:
        """Run all session init hooks. Returns list of context injection texts."""
        injections: list[str] = []
        for hook in self._hooks:
            try:
                text = await hook.on_session_init(context)
                if text:
                    injections.append(text)
            except Exception as e:
                logger.error("hook_session_init_failed", hook=hook.name, error=str(e))
        return injections

    async def run_pre_hooks(
        self,
        tool_name: str,
        arguments: dict,
        context: HookContext,
    ) -> PreToolUseResult:
        """Run all PreToolUse hooks. First DENY wins.

        REL-02: Individual hook failures are isolated — a broken hook
        doesn't prevent the remaining hooks from running.
        """
        current_args = dict(arguments)
        for hook in self._hooks:
            try:
                result = await hook.pre_tool_use(tool_name, current_args, context)
                if result.action == HookAction.DENY:
                    logger.info(
                        "hook_denied_tool",
                        hook=hook.name,
                        tool=tool_name,
                        reason=result.deny_reason,
                    )
                    return result
                if result.action == HookAction.MODIFY and result.modified_arguments is not None:
                    current_args = result.modified_arguments
            except Exception as e:
                logger.error("hook_pre_failed", hook=hook.name, tool=tool_name, error=str(e))
        return PreToolUseResult(action=HookAction.ALLOW, modified_arguments=current_args)

    async def run_post_hooks(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        """Run all PostToolUse hooks. Modifications chain.

        REL-02: Individual hook failures are isolated.
        """
        current_result = result
        final = PostToolUseResult()
        for hook in self._hooks:
            try:
                hook_result = await hook.post_tool_use(
                    tool_name, arguments, current_result, is_error, context
                )
                if hook_result.modified_result is not None:
                    current_result = hook_result.modified_result
                    final.modified_result = current_result
                if hook_result.trigger_learning:
                    final.trigger_learning = True
            except Exception as e:
                logger.error("hook_post_failed", hook=hook.name, tool=tool_name, error=str(e))
        return final

    async def run_final_response_hooks(
        self,
        response: str,
        context: HookContext,
    ) -> FinalResponseResult:
        """Run all final-response hooks. Modifications chain."""
        current_response = response
        final = FinalResponseResult()
        for hook in self._hooks:
            try:
                hook_result = await hook.on_final_response(current_response, context)
                if hook_result.modified_response is not None:
                    current_response = hook_result.modified_response
                    final.modified_response = current_response
                if hook_result.requires_followup:
                    final.requires_followup = True
                    if hook_result.followup_reason:
                        final.followup_reason = hook_result.followup_reason
            except Exception as e:
                logger.error("hook_final_response_failed", hook=hook.name, error=str(e))
        return final
