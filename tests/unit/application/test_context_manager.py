"""ContextManager tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ds_agent.agent.context_manager import ContextManager
from ds_agent.domain.entities.messages import ChatMessage, Role, ToolCall, Usage


class TestContextManager:
    def test_should_compress_false_under_threshold(self):
        provider = MagicMock()
        provider.count_tokens = AsyncMock(return_value=1000)
        provider.get_model_info = MagicMock(return_value=MagicMock(max_context_tokens=100_000))

        cm = ContextManager(provider=provider, threshold_pct=80.0)
        messages = [ChatMessage(role=Role.USER, content="Short")]

        result = cm.should_compress(messages, current_tokens=1000)
        assert result is False

    def test_should_compress_true_over_threshold(self):
        provider = MagicMock()
        provider.get_model_info = MagicMock(return_value=MagicMock(max_context_tokens=100_000))

        cm = ContextManager(provider=provider, threshold_pct=80.0)

        # 80% of 100K = 80K
        result = cm.should_compress([], current_tokens=85_000)
        assert result is True

    @pytest.mark.asyncio
    async def test_compress_keeps_system_and_recent(self):
        provider = MagicMock()
        provider.chat = AsyncMock(
            return_value=MagicMock(
                content="Summary of conversation",
                usage=Usage(input_tokens=50, output_tokens=20),
            )
        )
        provider.get_model_info = MagicMock(return_value=MagicMock(max_context_tokens=100_000))

        cm = ContextManager(provider=provider, keep_recent=2)

        messages = [
            ChatMessage(role=Role.SYSTEM, content="System prompt"),
            ChatMessage(role=Role.USER, content="Old message 1"),
            ChatMessage(role=Role.ASSISTANT, content="Old reply 1"),
            ChatMessage(role=Role.USER, content="Old message 2"),
            ChatMessage(role=Role.ASSISTANT, content="Old reply 2"),
            ChatMessage(role=Role.USER, content="Recent message"),
            ChatMessage(role=Role.ASSISTANT, content="Recent reply"),
        ]

        compressed = await cm.compress(messages)

        # Should keep: system + summary + last 2 messages
        assert compressed[0].role == Role.SYSTEM
        assert compressed[0].content == "System prompt"
        # Summary should be injected
        assert any("Summary" in (m.content or "") for m in compressed)
        # Recent messages preserved
        assert compressed[-1].content == "Recent reply"
        assert compressed[-2].content == "Recent message"

    @pytest.mark.asyncio
    async def test_compress_falls_back_on_llm_failure(self):
        """LLM raises during compression → original messages returned unchanged."""
        provider = MagicMock()
        provider.chat = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        provider.get_model_info = MagicMock(return_value=MagicMock(max_context_tokens=100_000))

        cm = ContextManager(provider=provider, keep_recent=2)

        messages = [
            ChatMessage(role=Role.SYSTEM, content="System"),
            ChatMessage(role=Role.USER, content="Old 1"),
            ChatMessage(role=Role.ASSISTANT, content="Old reply 1"),
            ChatMessage(role=Role.USER, content="Recent"),
            ChatMessage(role=Role.ASSISTANT, content="Recent reply"),
        ]

        result = await cm.compress(messages)

        # Must return original messages unchanged on failure
        assert result == messages

    @pytest.mark.asyncio
    async def test_compress_falls_back_on_timeout(self):
        """Compression LLM times out → original messages returned unchanged."""
        from unittest.mock import patch

        provider = MagicMock()
        provider.get_model_info = MagicMock(return_value=MagicMock(max_context_tokens=100_000))

        cm = ContextManager(provider=provider, keep_recent=2)

        messages = [
            ChatMessage(role=Role.SYSTEM, content="System"),
            ChatMessage(role=Role.USER, content="Old"),
            ChatMessage(role=Role.ASSISTANT, content="Old reply"),
            ChatMessage(role=Role.USER, content="Recent"),
            ChatMessage(role=Role.ASSISTANT, content="Recent reply"),
        ]

        # Simulate timeout by patching asyncio.wait_for to raise TimeoutError
        with patch(
            "ds_agent.agent.context_manager.asyncio.wait_for",
            side_effect=TimeoutError(),
        ):
            result = await cm.compress(messages)

        assert result == messages

    @pytest.mark.asyncio
    async def test_no_compression_when_few_messages(self):
        """If non-system messages ≤ keep_recent, compress returns original."""
        provider = MagicMock()
        provider.get_model_info = MagicMock(return_value=MagicMock(max_context_tokens=100_000))

        cm = ContextManager(provider=provider, keep_recent=4)

        messages = [
            ChatMessage(role=Role.SYSTEM, content="System"),
            ChatMessage(role=Role.USER, content="Q1"),
            ChatMessage(role=Role.ASSISTANT, content="A1"),
        ]

        # 2 non-system messages, keep_recent=4 → no compression needed
        result = await cm.compress(messages)
        assert result == messages

    @pytest.mark.asyncio
    async def test_compress_includes_tool_call_names_in_summary(self):
        """Tool calls in old messages → tool names appear in summary input, not '[tool call]'."""
        captured_text: list[str] = []

        async def capture_chat(messages, **kwargs):
            captured_text.append(messages[0].content or "")
            return MagicMock(
                content="Summary",
                usage=Usage(input_tokens=10, output_tokens=5),
            )

        provider = MagicMock()
        provider.chat = capture_chat
        provider.get_model_info = MagicMock(return_value=MagicMock(max_context_tokens=100_000))

        cm = ContextManager(provider=provider, keep_recent=2)

        messages = [
            ChatMessage(role=Role.SYSTEM, content="Sys"),
            ChatMessage(
                role=Role.ASSISTANT,
                tool_calls=[
                    ToolCall(id="tc1", name="train_model", arguments={}),
                    ToolCall(id="tc2", name="evaluate_model", arguments={}),
                ],
                content=None,
            ),
            ChatMessage(role=Role.USER, content="Recent 1"),
            ChatMessage(role=Role.ASSISTANT, content="Recent 2"),
        ]

        await cm.compress(messages)

        # Tool names must appear in the summarization prompt, not generic placeholder
        assert len(captured_text) == 1
        prompt = captured_text[0]
        assert "train_model" in prompt
        assert "evaluate_model" in prompt

    @pytest.mark.asyncio
    async def test_compress_re_emits_continuity_block_from_previous_summary(self):
        provider = MagicMock()
        provider.chat = AsyncMock(
            return_value=MagicMock(
                content="Compressed summary body",
                usage=Usage(input_tokens=20, output_tokens=10),
            )
        )
        provider.get_model_info = MagicMock(return_value=MagicMock(max_context_tokens=100_000))

        cm = ContextManager(provider=provider, keep_recent=2)
        messages = [
            ChatMessage(role=Role.SYSTEM, content="System"),
            ChatMessage(
                role=Role.ASSISTANT,
                content=(
                    "[Conversation Summary]\n\n"
                    "[Continuity State]\n"
                    "- Current stage: profiling\n"
                    "- Blocker: Which target column should be used?\n"
                    "- Next step: Inspect missingness by column.\n\n"
                    "Older compressed details."
                ),
            ),
            ChatMessage(role=Role.USER, content="Recent 1"),
            ChatMessage(role=Role.ASSISTANT, content="Recent 2"),
        ]

        compressed = await cm.compress(messages)

        summary = compressed[1].content or ""
        assert "[Continuity State]" in summary
        assert "- Current stage: profiling" in summary
        assert "Which target column should be used?" in summary
        assert "Inspect missingness by column" in summary

    @pytest.mark.asyncio
    async def test_compress_passes_explicit_continuity_state_to_summary_prompt(self):
        captured_text: list[str] = []

        async def capture_chat(messages, **kwargs):
            captured_text.append(messages[0].content or "")
            return MagicMock(
                content="Summary",
                usage=Usage(input_tokens=10, output_tokens=5),
            )

        provider = MagicMock()
        provider.chat = capture_chat
        provider.get_model_info = MagicMock(return_value=MagicMock(max_context_tokens=100_000))

        cm = ContextManager(provider=provider, keep_recent=2)
        messages = [
            ChatMessage(role=Role.SYSTEM, content="System"),
            ChatMessage(
                role=Role.ASSISTANT,
                content=(
                    "# Execution Continuity\n"
                    "- Current stage: profiling\n"
                    "- Active blocker: Which target column should be used?\n"
                    "- Next step: Inspect missingness by column."
                ),
            ),
            ChatMessage(role=Role.USER, content="Recent 1"),
            ChatMessage(role=Role.ASSISTANT, content="Recent 2"),
        ]

        await cm.compress(messages)

        prompt = captured_text[0]
        assert "Known continuity state that must survive verbatim if present:" in prompt
        assert "- Current stage: profiling" in prompt
        assert "- Blocker: Which target column should be used?" in prompt
        assert "- Next step: Inspect missingness by column" in prompt
