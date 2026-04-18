"""Tests for providers/base.py — message conversion and response parsing utilities."""

from __future__ import annotations

from unittest.mock import MagicMock

from ds_agent.domain.entities.messages import ChatMessage, Role, ToolCall
from ds_agent.providers.base import messages_to_openai_format, openai_response_to_llm_response


class TestMessagesToOpenAIFormat:
    def test_simple_user_message(self):
        messages = [ChatMessage(role=Role.USER, content="Hello")]
        result = messages_to_openai_format(messages)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"

    def test_system_message(self):
        messages = [ChatMessage(role=Role.SYSTEM, content="You are a DS agent")]
        result = messages_to_openai_format(messages)
        assert result[0]["role"] == "system"

    def test_assistant_with_tool_calls(self):
        messages = [
            ChatMessage(
                role=Role.ASSISTANT,
                content=None,
                tool_calls=[
                    ToolCall(id="tc_1", name="read_file", arguments={"path": "data.csv"}),
                ],
            )
        ]
        result = messages_to_openai_format(messages)
        assert "tool_calls" in result[0]
        assert result[0]["tool_calls"][0]["function"]["name"] == "read_file"
        # When tool_calls present, content is popped
        assert "content" not in result[0]

    def test_tool_result_message(self):
        messages = [
            ChatMessage(
                role=Role.TOOL,
                content="file contents here",
                tool_call_id="tc_1",
                name="read_file",
            )
        ]
        result = messages_to_openai_format(messages)
        assert result[0]["role"] == "tool"
        assert result[0]["tool_call_id"] == "tc_1"
        assert result[0]["name"] == "read_file"

    def test_none_content_becomes_empty_string(self):
        messages = [ChatMessage(role=Role.USER, content=None)]
        result = messages_to_openai_format(messages)
        assert result[0]["content"] == ""


class TestOpenAIResponseToLLMResponse:
    def test_text_response(self):
        message = MagicMock()
        message.content = "Hello world"
        message.tool_calls = None
        choice = MagicMock()
        choice.message = message
        choice.finish_reason = "stop"
        usage = MagicMock()
        usage.prompt_tokens = 100
        usage.completion_tokens = 50
        usage.cache_read_input_tokens = 0
        usage.reasoning_tokens = 0
        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = usage
        resp.model = "gpt-4.1"

        result = openai_response_to_llm_response(resp)
        assert result.content == "Hello world"
        assert result.tool_calls is None
        assert result.usage.input_tokens == 100

    def test_tool_call_response(self):
        func = MagicMock()
        func.name = "read_file"
        func.arguments = '{"path": "data.csv"}'
        tc = MagicMock()
        tc.id = "call_1"
        tc.type = "function"
        tc.function = func
        message = MagicMock()
        message.content = None
        message.tool_calls = [tc]
        choice = MagicMock()
        choice.message = message
        choice.finish_reason = "tool_calls"
        usage = MagicMock()
        usage.prompt_tokens = 50
        usage.completion_tokens = 10
        usage.cache_read_input_tokens = 0
        usage.reasoning_tokens = 0
        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = usage
        resp.model = "gpt-4.1"

        result = openai_response_to_llm_response(resp)
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "read_file"
        assert result.tool_calls[0].arguments == {"path": "data.csv"}

    def test_malformed_tool_call_arguments(self):
        """REL-10: Malformed JSON in tool call arguments should not crash."""
        func = MagicMock()
        func.name = "read_file"
        func.arguments = "not valid json {"
        tc = MagicMock()
        tc.id = "call_1"
        tc.type = "function"
        tc.function = func
        message = MagicMock()
        message.content = None
        message.tool_calls = [tc]
        choice = MagicMock()
        choice.message = message
        choice.finish_reason = "tool_calls"
        usage = MagicMock()
        usage.prompt_tokens = 50
        usage.completion_tokens = 10
        usage.cache_read_input_tokens = 0
        usage.reasoning_tokens = 0
        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = usage
        resp.model = "gpt-4.1"

        result = openai_response_to_llm_response(resp)
        assert result.tool_calls is not None
        # Should use _raw fallback
        assert result.tool_calls[0].arguments == {"_raw": "not valid json {"}
