"""Domain entity tests: ChatMessage, ToolCall, LLMResponse, Usage."""

from dataclasses import asdict

from ds_agent.domain.entities.messages import (
    ChatMessage,
    LLMResponse,
    Role,
    ToolCall,
    ToolResult,
    Usage,
)


class TestChatMessage:
    def test_system_message(self):
        msg = ChatMessage(role=Role.SYSTEM, content="You are a DS agent.")
        assert msg.role == Role.SYSTEM
        assert msg.content == "You are a DS agent."
        assert msg.tool_calls is None

    def test_user_message(self):
        msg = ChatMessage(role=Role.USER, content="Analyze this data.")
        assert msg.role == Role.USER
        assert msg.content == "Analyze this data."

    def test_assistant_message_with_tool_calls(self):
        tc = ToolCall(id="call_1", name="profile_data", arguments={"file": "data.csv"})
        msg = ChatMessage(role=Role.ASSISTANT, content=None, tool_calls=[tc])
        assert msg.role == Role.ASSISTANT
        assert msg.content is None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "profile_data"

    def test_tool_result_message(self):
        msg = ChatMessage(
            role=Role.TOOL,
            content='{"rows": 1000}',
            tool_call_id="call_1",
            name="profile_data",
        )
        assert msg.role == Role.TOOL
        assert msg.tool_call_id == "call_1"


class TestToolCall:
    def test_creation(self):
        tc = ToolCall(id="tc_1", name="eda", arguments={"columns": ["age", "income"]})
        assert tc.id == "tc_1"
        assert tc.name == "eda"
        assert tc.arguments == {"columns": ["age", "income"]}

    def test_serialization_roundtrip(self):
        tc = ToolCall(id="tc_1", name="model_train", arguments={"algo": "xgboost", "cv": 5})
        data = asdict(tc)
        tc2 = ToolCall(**data)
        assert tc == tc2

    def test_empty_arguments(self):
        tc = ToolCall(id="tc_1", name="list_tools", arguments={})
        assert tc.arguments == {}


class TestToolResult:
    def test_success_result(self):
        tr = ToolResult(tool_call_id="tc_1", content='{"accuracy": 0.95}')
        assert not tr.is_error

    def test_error_result(self):
        tr = ToolResult(tool_call_id="tc_1", content="FileNotFoundError", is_error=True)
        assert tr.is_error


class TestUsage:
    def test_total_tokens(self):
        u = Usage(input_tokens=1000, output_tokens=500)
        assert u.total_tokens == 1500

    def test_total_tokens_with_reasoning(self):
        u = Usage(input_tokens=1000, output_tokens=500, reasoning_tokens=200)
        assert u.total_tokens == 1700

    def test_total_tokens_with_cache(self):
        u = Usage(input_tokens=1000, output_tokens=500, cache_read_tokens=300)
        # cache_read_tokens are NOT counted in total (they replace input_tokens)
        assert u.total_tokens == 1500

    def test_default_values(self):
        u = Usage()
        assert u.total_tokens == 0


class TestLLMResponse:
    def test_text_only_response(self):
        resp = LLMResponse(
            content="The dataset has 1000 rows.",
            usage=Usage(input_tokens=100, output_tokens=50),
            model="claude-sonnet-4",
            stop_reason="end_turn",
        )
        assert resp.content == "The dataset has 1000 rows."
        assert resp.tool_calls is None
        assert resp.usage.total_tokens == 150

    def test_tool_calls_response(self):
        tc = ToolCall(id="tc_1", name="profile_data", arguments={"file": "data.csv"})
        resp = LLMResponse(
            content=None,
            tool_calls=[tc],
            usage=Usage(input_tokens=200, output_tokens=100),
            model="claude-sonnet-4",
            stop_reason="tool_use",
        )
        assert resp.content is None
        assert len(resp.tool_calls) == 1
        assert resp.stop_reason == "tool_use"

    def test_thinking_response(self):
        resp = LLMResponse(
            content="Result",
            thinking="Let me think step by step...",
            usage=Usage(input_tokens=100, output_tokens=50, reasoning_tokens=200),
        )
        assert resp.thinking is not None
        assert resp.usage.reasoning_tokens == 200

    def test_default_values(self):
        resp = LLMResponse()
        assert resp.content is None
        assert resp.tool_calls is None
        assert resp.model == ""
        assert resp.usage.total_tokens == 0
