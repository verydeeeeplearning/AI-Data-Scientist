"""Context compression manager."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

import structlog

from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.interfaces.llm_provider import LLMProvider
from ds_agent.domain.value_objects.analysis_stage import AnalysisStage

logger = structlog.get_logger()

COMPRESSION_PROMPT = """\
Summarize the following data science conversation concisely.
Preserve ALL of the following that appear:
- Key decisions and rationale
- Active workflow stage and stage-specific blockers
- The exact next step the agent planned to take
- Tool calls made and their outcomes (tool name, key results/numbers)
- Dataset characteristics (shape, columns, types, missing values)
- Model performance metrics and comparisons
- Errors encountered and how they were resolved
- Findings and conclusions

This summary replaces the original messages to save context window space.
Be specific with numbers and names; do NOT paraphrase metric values.

Known continuity state that must survive verbatim if present:
{continuity_state}

Conversation to summarize:
{conversation}
"""

_CURRENT_STAGE_PATTERN = re.compile(
    r"(?im)^\s*[-*]\s*(?:current stage|stage)\s*:\s*(?P<value>.+?)\s*$"
)
_BLOCKER_PATTERN = re.compile(
    r"(?im)^\s*[-*]\s*(?:active blocker|blocker)\s*:\s*(?P<value>.+?)\s*$"
)
_NEXT_STEP_PATTERN = re.compile(
    r"(?im)^\s*[-*]\s*(?:next step|suggested next step)\s*:\s*(?P<value>.+?)\s*$"
)
_PENDING_INLINE_PATTERN = re.compile(
    r"(?im)^\s*[-*]\s*(?:pending question|pending questions)\s*:\s*(?P<value>.+?)\s*$"
)
_QUESTION_HINTS = ("please provide", "which ", "what ", "confirm", "clarify")


@dataclass(slots=True)
class _ContinuityState:
    current_stage: AnalysisStage | None = None
    blocker: str | None = None
    next_step: str | None = None

    def has_content(self) -> bool:
        return self.current_stage is not None or bool(self.blocker) or bool(self.next_step)


class ContextManager:
    """Manages context window by compressing old messages when nearing the limit."""

    def __init__(
        self,
        provider: LLMProvider,
        threshold_pct: float = 80.0,
        keep_recent: int = 4,
    ) -> None:
        self._provider = provider
        self._threshold_pct = threshold_pct
        self._keep_recent = keep_recent

    def should_compress(
        self,
        messages: list[ChatMessage],
        current_tokens: int = 0,
    ) -> bool:
        """Check if compression is needed based on token count vs context window."""
        model_info = self._provider.get_model_info()
        max_tokens = model_info.max_context_tokens
        threshold = max_tokens * (self._threshold_pct / 100)
        return current_tokens > threshold

    async def compress(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """Compress middle messages into a summary, keeping system and recent."""
        system_msgs = [m for m in messages if m.role == Role.SYSTEM]
        non_system = [m for m in messages if m.role != Role.SYSTEM]

        if len(non_system) <= self._keep_recent:
            return messages

        old_msgs = non_system[: -self._keep_recent]
        recent_msgs = non_system[-self._keep_recent :]

        def _msg_summary(message: ChatMessage) -> str:
            role = message.role.value
            if message.content:
                preview = message.content[:300].replace("\n", " ")
                return f"{role}: {preview}"
            if message.tool_calls:
                names = ", ".join(tc.name for tc in message.tool_calls)
                return f"{role}: [calls: {names}]"
            if message.tool_call_id:
                content_preview = (message.content or "")[:150].replace("\n", " ")
                return f"{role}: [tool_result id={message.tool_call_id}] {content_preview}"
            return f"{role}: [no content]"

        conversation_text = "\n".join(_msg_summary(message) for message in old_msgs)
        continuity_state = _extract_continuity_state(old_msgs)
        summary_prompt = COMPRESSION_PROMPT.format(
            continuity_state=_format_prompt_continuity_state(continuity_state),
            conversation=conversation_text,
        )

        try:
            summary_response = await asyncio.wait_for(
                self._provider.chat(
                    messages=[ChatMessage(role=Role.USER, content=summary_prompt)],
                ),
                timeout=30,
            )
        except Exception as exc:
            logger.warning("compression_failed_using_original", error=str(exc))
            return messages

        summary_parts = ["[Conversation Summary]"]
        continuity_block = _format_summary_continuity_block(continuity_state)
        if continuity_block:
            summary_parts.append(continuity_block)
        if summary_response.content:
            summary_parts.append(summary_response.content)

        summary_msg = ChatMessage(
            role=Role.ASSISTANT,
            content="\n\n".join(summary_parts),
        )

        return [*system_msgs, summary_msg, *recent_msgs]


def _extract_continuity_state(messages: list[ChatMessage]) -> _ContinuityState:
    state = _ContinuityState()
    for message in reversed(messages):
        content = (message.content or "").strip()
        if not content:
            continue
        if state.current_stage is None:
            state.current_stage = _extract_stage(content)
        if not state.blocker:
            state.blocker = _extract_blocker(content)
        if not state.next_step:
            state.next_step = _extract_field(content, _NEXT_STEP_PATTERN)
        if state.current_stage is not None and state.blocker and state.next_step:
            break
    return state


def _extract_stage(text: str) -> AnalysisStage | None:
    extracted = _extract_field(text, _CURRENT_STAGE_PATTERN)
    if extracted is None:
        return None

    normalized = re.sub(r"[^a-z_ ]+", " ", extracted.lower()).replace("_", " ")
    normalized = " ".join(normalized.split())
    for stage in AnalysisStage:
        if normalized == stage.value.replace("_", " "):
            return stage
    return None


def _extract_blocker(text: str) -> str | None:
    direct = _extract_field(text, _BLOCKER_PATTERN)
    if direct:
        return direct

    inline_pending = _extract_field(text, _PENDING_INLINE_PATTERN)
    if inline_pending:
        return inline_pending

    nested_pending = _extract_pending_question(text)
    if nested_pending:
        return nested_pending

    for candidate in reversed(re.findall(r"[^.!?\n]*\?+", text)):
        cleaned = _clean_continuity_value(candidate)
        lowered = cleaned.lower()
        if any(token in lowered for token in _QUESTION_HINTS):
            return cleaned
    return None


def _extract_pending_question(text: str) -> str | None:
    capture_nested = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        lowered = stripped.lower()
        if not stripped:
            continue
        if lowered in {"- pending questions:", "* pending questions:"}:
            capture_nested = True
            continue
        if capture_nested:
            match = re.match(r"^[-*]\s+(.+?)\s*$", stripped)
            if match:
                return _clean_continuity_value(match.group(1))
            capture_nested = False
    return None


def _extract_field(text: str, pattern: re.Pattern[str]) -> str | None:
    matches = list(pattern.finditer(text))
    if not matches:
        return None
    return _clean_continuity_value(matches[-1].group("value"))


def _clean_continuity_value(value: str) -> str:
    return " ".join(value.split()).strip().strip("-*")


def _format_prompt_continuity_state(state: _ContinuityState) -> str:
    if not state.has_content():
        return "- No explicit current stage, blocker, or next step recorded."

    lines: list[str] = []
    if state.current_stage is not None:
        lines.append(f"- Current stage: {state.current_stage.value}")
    if state.blocker:
        lines.append(f"- Blocker: {state.blocker}")
    if state.next_step:
        lines.append(f"- Next step: {state.next_step}")
    return "\n".join(lines)


def _format_summary_continuity_block(state: _ContinuityState) -> str:
    if not state.has_content():
        return ""

    lines = ["[Continuity State]"]
    if state.current_stage is not None:
        lines.append(f"- Current stage: {state.current_stage.value}")
    if state.blocker:
        lines.append(f"- Blocker: {state.blocker}")
    if state.next_step:
        lines.append(f"- Next step: {state.next_step}")
    return "\n".join(lines)
