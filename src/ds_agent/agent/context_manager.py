"""Context compression manager."""

from __future__ import annotations

import asyncio

import structlog

from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.interfaces.llm_provider import LLMProvider

logger = structlog.get_logger()

COMPRESSION_PROMPT = """\
Summarize the following data science conversation concisely.
Preserve ALL of the following that appear:
- Key decisions and rationale
- Tool calls made and their outcomes (tool name, key results/numbers)
- Dataset characteristics (shape, columns, types, missing values)
- Model performance metrics and comparisons
- Errors encountered and how they were resolved
- Findings and conclusions

This summary replaces the original messages to save context window space.
Be specific with numbers and names — do NOT paraphrase metric values.

Conversation to summarize:
{conversation}
"""


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
        # Separate system messages
        system_msgs = [m for m in messages if m.role == Role.SYSTEM]
        non_system = [m for m in messages if m.role != Role.SYSTEM]

        if len(non_system) <= self._keep_recent:
            return messages  # Nothing to compress

        # Split into old (to summarize) and recent (to keep)
        old_msgs = non_system[: -self._keep_recent]
        recent_msgs = non_system[-self._keep_recent :]

        # 4.11 fix: include tool names/results instead of generic placeholder
        def _msg_summary(m: ChatMessage) -> str:
            role = m.role.value
            if m.content:
                preview = m.content[:300].replace("\n", " ")
                return f"{role}: {preview}"
            if m.tool_calls:
                names = ", ".join(tc.name for tc in m.tool_calls)
                return f"{role}: [calls: {names}]"
            if m.tool_call_id:
                content_preview = (m.content or "")[:150].replace("\n", " ")
                return f"{role}: [tool_result id={m.tool_call_id}] {content_preview}"
            return f"{role}: [no content]"

        # Build summary using LLM
        conversation_text = "\n".join(_msg_summary(m) for m in old_msgs)

        summary_prompt = COMPRESSION_PROMPT.format(conversation=conversation_text)

        # REL-03: Compression failure falls back to keeping original messages
        try:
            summary_response = await asyncio.wait_for(
                self._provider.chat(
                    messages=[ChatMessage(role=Role.USER, content=summary_prompt)],
                ),
                timeout=30,
            )
        except Exception as e:
            logger.warning("compression_failed_using_original", error=str(e))
            return messages  # Fallback: return original messages

        summary_msg = ChatMessage(
            role=Role.ASSISTANT,
            content=f"[Conversation Summary]\n{summary_response.content}",
        )

        return [*system_msgs, summary_msg, *recent_msgs]
