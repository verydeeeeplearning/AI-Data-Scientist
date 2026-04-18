"""Tests for Codex Responses API conversion helpers."""

from __future__ import annotations

from types import SimpleNamespace

from ds_agent.domain.entities.messages import ChatMessage, Role, ToolCall
from ds_agent.providers.base import (
    messages_to_responses_input,
    openai_tools_to_responses_format,
    responses_response_to_llm_response,
)


class TestMessagesToResponsesInput:
    def test_converts_message_history_with_tool_roundtrip(self):
        messages = [
            ChatMessage(role=Role.SYSTEM, content="You are a DS agent"),
            ChatMessage(role=Role.USER, content="Analyze data.csv"),
            ChatMessage(
                role=Role.ASSISTANT,
                content="I will inspect the file first.",
                tool_calls=[
                    ToolCall(id="call_1", name="read_file", arguments={"path": "data.csv"}),
                ],
            ),
            ChatMessage(
                role=Role.TOOL,
                content='{"rows": 10}',
                tool_call_id="call_1",
                name="read_file",
            ),
        ]

        result = messages_to_responses_input(messages)

        assert result == [
            {
                "type": "message",
                "role": "system",
                "content": [{"type": "input_text", "text": "You are a DS agent"}],
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Analyze data.csv"}],
            },
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": "I will inspect the file first.",
                        "annotations": [],
                    }
                ],
            },
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "read_file",
                "arguments": '{"path": "data.csv"}',
            },
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": '{"rows": 10}',
            },
        ]


class TestOpenAIToolsToResponsesFormat:
    def test_converts_chat_completions_tool_schema(self):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file from disk",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
                },
            }
        ]

        result = openai_tools_to_responses_format(tools)

        assert result == [
            {
                "type": "function",
                "name": "read_file",
                "description": "Read a file from disk",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            }
        ]


class TestResponsesResponseToLLMResponse:
    def test_parses_text_usage_and_reasoning_summary(self):
        response = SimpleNamespace(
            output_text="Analysis complete",
            output=[
                SimpleNamespace(
                    type="reasoning",
                    summary=[SimpleNamespace(text="Verified schema and missing values.")],
                ),
                SimpleNamespace(
                    type="message",
                    role="assistant",
                    content=[SimpleNamespace(type="output_text", text="Analysis complete")],
                ),
            ],
            usage=SimpleNamespace(
                input_tokens=120,
                output_tokens=40,
                input_tokens_details=SimpleNamespace(cached_tokens=20),
                output_tokens_details=SimpleNamespace(reasoning_tokens=7),
            ),
            model="gpt-5.4",
            status="completed",
        )

        result = responses_response_to_llm_response(response)

        assert result.content == "Analysis complete"
        assert result.thinking == "Verified schema and missing values."
        assert result.tool_calls is None
        assert result.usage.input_tokens == 100
        assert result.usage.output_tokens == 40
        assert result.usage.cache_read_tokens == 20
        assert result.usage.reasoning_tokens == 7
        assert result.stop_reason == "stop"

    def test_parses_tool_call_using_call_id(self):
        response = SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="function_call",
                    id="fc_123",
                    call_id="call_abc",
                    name="profile_data",
                    arguments='{"file": "data.csv"}',
                )
            ],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=0,
                input_tokens_details=None,
                output_tokens_details=None,
            ),
            model="gpt-5.4",
            status="completed",
        )

        result = responses_response_to_llm_response(response)

        assert result.content is None
        assert result.tool_calls is not None
        assert result.tool_calls[0].id == "call_abc"
        assert result.tool_calls[0].name == "profile_data"
        assert result.tool_calls[0].arguments == {"file": "data.csv"}
        assert result.stop_reason == "tool_calls"

    def test_malformed_tool_call_arguments_use_raw_fallback(self):
        response = SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="function_call",
                    call_id="call_bad",
                    name="read_file",
                    arguments="not valid json {",
                )
            ],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=0,
                input_tokens_details=None,
                output_tokens_details=None,
            ),
            model="gpt-5.4",
            status="completed",
        )

        result = responses_response_to_llm_response(response)

        assert result.tool_calls is not None
        assert result.tool_calls[0].arguments == {"_raw": "not valid json {"}
