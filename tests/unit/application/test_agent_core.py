"""DSAgent core loop tests with mock provider and tools."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ds_agent.agent.core import DSAgent
from ds_agent.agent.ds_workflow_hooks import WorkflowTrackerHook
from ds_agent.agent.hooks import FinalResponseResult, HookContext, HookRegistry, ToolHook
from ds_agent.agent.prompt_builder import PromptBuilder
from ds_agent.domain.entities.goal import GoalStatus
from ds_agent.domain.entities.messages import (
    ChatMessage,
    LLMResponse,
    Role,
    ToolCall,
    Usage,
)
from ds_agent.domain.entities.session_checkpoint import SessionCheckpoint
from ds_agent.domain.entities.task_contract import DeliverableSpec, TaskContract, TaskContractStatus
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.result_card import ResultCardSource, coerce_result_card
from ds_agent.domain.value_objects.analysis_stage import AnalysisStage
from ds_agent.domain.value_objects.budget import BudgetPolicy


class TestDSAgentCore:
    @pytest.mark.asyncio
    async def test_single_text_response(self, make_mock_provider, make_mock_tool_registry):
        """LLM returns text only → agent completes immediately."""
        provider = make_mock_provider(
            [
                LLMResponse(
                    content="The data has 1000 rows.",
                    usage=Usage(input_tokens=100, output_tokens=50),
                )
            ]
        )

        agent = DSAgent(provider=provider, tool_registry=make_mock_tool_registry())
        result = await agent.run("How many rows?")

        assert result == "The data has 1000 rows."
        provider.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_call_then_text(self, make_mock_provider, make_mock_tool_registry):
        """LLM calls tool → gets result → returns text."""
        provider = make_mock_provider(
            [
                # First: tool call
                LLMResponse(
                    tool_calls=[ToolCall(id="tc1", name="count_rows", arguments={})],
                    usage=Usage(input_tokens=100, output_tokens=50),
                ),
                # Second: text response after seeing tool result
                LLMResponse(
                    content="The dataset has 1000 rows.",
                    usage=Usage(input_tokens=200, output_tokens=50),
                ),
            ]
        )

        tools = {"count_rows": lambda: 1000}
        agent = DSAgent(provider=provider, tool_registry=make_mock_tool_registry(tools))
        result = await agent.run("Count rows")

        assert result == "The dataset has 1000 rows."
        assert provider.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_in_one_turn(
        self, make_mock_provider, make_mock_tool_registry
    ):
        """LLM calls multiple tools in one turn."""
        provider = make_mock_provider(
            [
                LLMResponse(
                    tool_calls=[
                        ToolCall(id="tc1", name="tool_a", arguments={}),
                        ToolCall(id="tc2", name="tool_b", arguments={}),
                    ],
                    usage=Usage(input_tokens=100, output_tokens=50),
                ),
                LLMResponse(
                    content="Both tools executed.",
                    usage=Usage(input_tokens=200, output_tokens=50),
                ),
            ]
        )

        tools = {"tool_a": lambda: "result_a", "tool_b": lambda: "result_b"}
        agent = DSAgent(provider=provider, tool_registry=make_mock_tool_registry(tools))
        result = await agent.run("Run both")

        assert result == "Both tools executed."

    @pytest.mark.asyncio
    async def test_budget_exhaustion(self, make_mock_provider, make_mock_tool_registry):
        """Agent stops when budget is exhausted."""
        responses = [
            LLMResponse(
                tool_calls=[ToolCall(id=f"tc{i}", name="noop", arguments={})],
                usage=Usage(input_tokens=100, output_tokens=50),
            )
            for i in range(10)
        ]
        provider = make_mock_provider(responses)

        tools = {"noop": lambda: "ok"}
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(tools),
            budget_policy=BudgetPolicy(max_iterations=3),
        )
        result = await agent.run("Loop forever")

        assert "budget" in result.lower() or "exhausted" in result.lower()

    @pytest.mark.asyncio
    async def test_callbacks_called(self, make_mock_provider, make_mock_tool_registry):
        """Callbacks are invoked during agent execution."""
        provider = make_mock_provider(
            [
                LLMResponse(
                    tool_calls=[ToolCall(id="tc1", name="my_tool", arguments={"x": 1})],
                    usage=Usage(input_tokens=100, output_tokens=50),
                ),
                LLMResponse(
                    content="Done.",
                    usage=Usage(input_tokens=200, output_tokens=50),
                ),
            ]
        )

        callbacks = MagicMock()
        callbacks.on_tool_start = AsyncMock()
        callbacks.on_tool_end = AsyncMock()
        callbacks.on_step = AsyncMock()
        callbacks.on_status = AsyncMock()
        callbacks.on_stream_delta = AsyncMock()
        callbacks.emit_event = MagicMock()

        tools = {"my_tool": lambda x=0: "result"}
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(tools),
            callbacks=callbacks,
        )
        await agent.run("Do something")

        callbacks.on_tool_start.assert_called_once()
        callbacks.on_tool_end.assert_called_once()
        assert callbacks.on_step.call_count >= 1

    @pytest.mark.asyncio
    async def test_empty_response_handled(self, make_mock_provider, make_mock_tool_registry):
        """LLM returns empty content → treated as completion."""
        provider = make_mock_provider(
            [
                LLMResponse(
                    content="",
                    usage=Usage(input_tokens=100, output_tokens=5),
                )
            ]
        )

        agent = DSAgent(provider=provider, tool_registry=make_mock_tool_registry())
        result = await agent.run("Hello")

        assert result == ""

    # --- Phase 2: Gap-filling tests ---

    @pytest.mark.asyncio
    async def test_llm_timeout_returns_error(self, make_mock_provider, make_mock_tool_registry):
        """LLM call timeout → Korean error message returned."""
        provider = make_mock_provider([])
        provider.chat = AsyncMock(side_effect=TimeoutError("timeout"))

        agent = DSAgent(provider=provider, tool_registry=make_mock_tool_registry())
        result = await agent.run("Hello")

        assert "타임아웃" in result

    @pytest.mark.asyncio
    async def test_llm_exception_returns_error(self, make_mock_provider, make_mock_tool_registry):
        """LLM call raises generic exception → error message returned."""
        provider = make_mock_provider([])
        provider.chat = AsyncMock(side_effect=RuntimeError("API down"))

        agent = DSAgent(provider=provider, tool_registry=make_mock_tool_registry())
        result = await agent.run("Hello")

        assert "오류" in result
        assert "API down" in result

    @pytest.mark.asyncio
    async def test_thinking_emitted(self, make_mock_provider, make_mock_tool_registry):
        """LLM response with thinking field → on_thinking callback invoked."""
        provider = make_mock_provider(
            [
                LLMResponse(
                    content="Answer.",
                    thinking="Let me reason about this...",
                    usage=Usage(input_tokens=100, output_tokens=50),
                )
            ]
        )

        callbacks = MagicMock()
        callbacks.on_step = AsyncMock()
        callbacks.on_status = AsyncMock()
        callbacks.on_thinking = AsyncMock()
        callbacks.on_budget_warning = AsyncMock()
        callbacks.on_stream_delta = AsyncMock()
        callbacks.emit_event = MagicMock()

        agent = DSAgent(
            provider=provider, tool_registry=make_mock_tool_registry(), callbacks=callbacks
        )
        result = await agent.run("Think about this")

        assert result == "Answer."
        callbacks.on_thinking.assert_called_once_with("Let me reason about this...")

    @pytest.mark.asyncio
    async def test_run_resets_budget_between_turns(
        self,
        make_mock_provider,
        make_mock_tool_registry,
    ):
        provider = make_mock_provider(
            [
                LLMResponse(
                    content="Analysis complete.",
                    usage=Usage(input_tokens=100, output_tokens=50),
                ),
                LLMResponse(
                    content="Analysis complete.",
                    usage=Usage(input_tokens=200, output_tokens=50),
                ),
            ]
        )

        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            budget_policy=BudgetPolicy(max_iterations=5),
        )

        await agent.run("First run")
        assert agent._budget.get_summary()["iterations_used"] == 1

        await agent.run("Second run")
        assert agent._budget.get_summary()["iterations_used"] == 1

    @pytest.mark.asyncio
    async def test_final_response_context_uses_current_turn_messages_and_active_contract(
        self,
        make_mock_provider,
        make_mock_tool_registry,
        tmp_path,
    ):
        provider = make_mock_provider(
            [
                LLMResponse(
                    content="Final answer.",
                    usage=Usage(input_tokens=100, output_tokens=50),
                )
            ]
        )
        captured: list[HookContext] = []

        class CaptureContextHook(ToolHook):
            name = "capture_context"
            priority = 5

            async def on_final_response(self, response, context):
                captured.append(context)
                return FinalResponseResult()

        contract_store = MagicMock()
        contract_store.get_active_bundle.return_value = TaskContractBundle(
            contract=TaskContract(
                task_id="TC-2026-123",
                session_id="session-ctx",
                type="analysis",
                status=TaskContractStatus.IN_PROGRESS,
                business_goal="Explain weekly retention movement.",
                required_deliverables=[
                    DeliverableSpec(type="exec_brief", audience="executive", format="md")
                ],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        hooks = HookRegistry()
        hooks.register(CaptureContextHook())
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            hook_registry=hooks,
            prompt_builder=PromptBuilder(
                workspace_dir=str(tmp_path),
                session_id="session-ctx",
                task_contract_store=contract_store,
            ),
            session_id="session-ctx",
        )

        result = await agent.run("Summarize the retention change.")

        assert result == "Final answer."
        assert captured
        assert captured[0].user_message == "Summarize the retention change."
        assert captured[0].recent_messages[-1].content == "Summarize the retention change."
        assert captured[0].active_task_contract is not None
        assert captured[0].active_task_contract.task_id == "TC-2026-123"
        assert captured[0].workspace_path == str(tmp_path)

    @pytest.mark.asyncio
    async def test_background_run_emits_task_completed_event(
        self,
        make_mock_provider,
        make_mock_tool_registry,
    ):
        provider = make_mock_provider(
            [
                LLMResponse(
                    content="Analysis complete.",
                    usage=Usage(input_tokens=100, output_tokens=50),
                )
            ]
        )

        callbacks = MagicMock()
        callbacks.on_step = AsyncMock()
        callbacks.on_status = AsyncMock()
        callbacks.on_thinking = AsyncMock()
        callbacks.on_budget_warning = AsyncMock()
        callbacks.on_stream_delta = AsyncMock()
        callbacks.emit_event = MagicMock()

        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            callbacks=callbacks,
        )
        await agent.run(
            "Background analysis",
            execution_mode="background",
            budget_policy=BudgetPolicy(max_iterations=3, max_cost_usd=0.25),
        )

        task_completed_payloads = [
            call.args[1]
            for call in callbacks.emit_event.call_args_list
            if call.args and call.args[0] == "task.completed"
        ]
        assert len(task_completed_payloads) == 1
        assert task_completed_payloads[0]["executionMode"] == "background"
        assert task_completed_payloads[0]["status"] == "completed"
        assert task_completed_payloads[0]["maxCostUsd"] == 0.25

    @pytest.mark.asyncio
    async def test_run_emits_task_started_and_progress_events(
        self,
        make_mock_provider,
        make_mock_tool_registry,
    ):
        provider = make_mock_provider(
            [
                LLMResponse(
                    content="Analysis complete.",
                    usage=Usage(input_tokens=100, output_tokens=50),
                )
            ]
        )

        callbacks = MagicMock()
        callbacks.on_step = AsyncMock()
        callbacks.on_status = AsyncMock()
        callbacks.on_thinking = AsyncMock()
        callbacks.on_budget_warning = AsyncMock()
        callbacks.on_stream_delta = AsyncMock()
        callbacks.emit_event = MagicMock()

        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            callbacks=callbacks,
        )
        await agent.run("Track lifecycle")

        emitted = [call.args[0] for call in callbacks.emit_event.call_args_list]
        assert "task.started" in emitted
        assert "task.progress" in emitted

    @pytest.mark.asyncio
    async def test_run_emits_mission_context_updates(
        self,
        tmp_path,
        make_mock_provider,
        make_mock_tool_registry,
    ):
        from ds_agent.runtime.goal_store import JsonGoalStore

        provider = make_mock_provider(
            [
                LLMResponse(
                    content="Analysis complete.",
                    usage=Usage(input_tokens=100, output_tokens=50),
                )
            ]
        )

        callbacks = MagicMock()
        callbacks.on_step = AsyncMock()
        callbacks.on_status = AsyncMock()
        callbacks.on_thinking = AsyncMock()
        callbacks.on_budget_warning = AsyncMock()
        callbacks.on_stream_delta = AsyncMock()
        callbacks.emit_event = MagicMock()

        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            callbacks=callbacks,
            session_id="mission-session",
            goal_store=JsonGoalStore(base_dir=tmp_path),
        )
        agent.set_runtime_context("run-mission-1", "ws")

        await agent.run("Build a churn model")

        mission_payloads = [
            call.args[1]
            for call in callbacks.emit_event.call_args_list
            if call.args and call.args[0] == "mission.context.updated"
        ]
        assert len(mission_payloads) >= 3
        assert all(payload["sessionId"] == "mission-session" for payload in mission_payloads)
        assert any(
            payload.get("goal", {}).get("title") == "Build a churn model"
            for payload in mission_payloads
        )
        assert any(
            payload.get("stage", {}).get("label") == "Analysis running"
            for payload in mission_payloads
        )
        assert any(
            payload.get("stage", {}).get("label") == "Completed" for payload in mission_payloads
        )
        assert any("budget" in payload for payload in mission_payloads)

    @pytest.mark.asyncio
    async def test_run_emits_task_failed_on_llm_timeout(
        self,
        make_mock_tool_registry,
    ):
        provider = MagicMock()
        provider.chat = AsyncMock(side_effect=TimeoutError("timeout"))
        provider.count_tokens = AsyncMock(return_value=100)
        provider.get_model_info = MagicMock()

        callbacks = MagicMock()
        callbacks.on_step = AsyncMock()
        callbacks.on_status = AsyncMock()
        callbacks.on_thinking = AsyncMock()
        callbacks.on_budget_warning = AsyncMock()
        callbacks.on_stream_delta = AsyncMock()
        callbacks.emit_event = MagicMock()

        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            callbacks=callbacks,
        )
        await agent.run("Trigger timeout")

        failure_payloads = [
            call.args[1]
            for call in callbacks.emit_event.call_args_list
            if call.args and call.args[0] == "task.failed"
        ]
        assert len(failure_payloads) == 1
        assert failure_payloads[0]["reason"] == "llm_timeout"

    @pytest.mark.asyncio
    async def test_run_can_resume_from_explicit_checkpoint(
        self,
        make_mock_provider,
        make_mock_tool_registry,
    ):
        provider = make_mock_provider(
            [
                LLMResponse(
                    content="Resumed successfully.",
                    usage=Usage(input_tokens=80, output_tokens=20),
                )
            ]
        )

        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            session_id="resume-session",
        )
        checkpoint = SessionCheckpoint(
            session_id="resume-session",
            step=5,
            messages=[ChatMessage(role=Role.USER, content="previous checkpoint context")],
        )

        result = await agent.run(
            "Continue from checkpoint",
            resume_from_checkpoint=checkpoint,
        )

        assert result == "Resumed successfully."
        first_call_messages = provider.chat.await_args.kwargs["messages"]
        assert first_call_messages[1].content == "previous checkpoint context"
        assert agent._step == 6

    @pytest.mark.asyncio
    async def test_hook_deny_blocks_tool(self, make_mock_provider, make_mock_tool_registry):
        """Pre-hook DENY → tool not executed, [DENIED] in result."""
        from ds_agent.agent.hooks import (
            HookAction,
            HookRegistry,
            PreToolUseResult,
            ToolHook,
        )

        class DenyAllHook(ToolHook):
            name = "deny_all"
            priority = 0

            async def pre_tool_use(self, tool_name, arguments, context):
                return PreToolUseResult(action=HookAction.DENY, deny_reason="blocked by test")

        hook_registry = HookRegistry()
        hook_registry.register(DenyAllHook())

        provider = make_mock_provider(
            [
                LLMResponse(
                    tool_calls=[ToolCall(id="tc1", name="my_tool", arguments={})],
                    usage=Usage(input_tokens=100, output_tokens=50),
                ),
                LLMResponse(
                    content="Tool was denied.",
                    usage=Usage(input_tokens=200, output_tokens=50),
                ),
            ]
        )

        callbacks = MagicMock()
        callbacks.on_step = AsyncMock()
        callbacks.on_status = AsyncMock()
        callbacks.on_tool_start = AsyncMock()
        callbacks.on_tool_end = AsyncMock()
        callbacks.on_budget_warning = AsyncMock()
        callbacks.on_stream_delta = AsyncMock()
        callbacks.emit_event = MagicMock()

        tools = {"my_tool": lambda: "should not run"}
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(tools),
            hook_registry=hook_registry,
            callbacks=callbacks,
        )
        await agent.run("Run tool")

        # Tool dispatch should NOT have been called
        # on_tool_end should receive the DENIED result
        callbacks.on_tool_end.assert_called_once()
        args = callbacks.on_tool_end.call_args
        assert "DENIED" in str(args)

    @pytest.mark.asyncio
    async def test_emit_file_created_for_write_file(self, tmp_path):
        """write_file tool with success → workspace and file events emitted."""
        agent = DSAgent(provider=MagicMock(), tool_registry=MagicMock())
        emit_mock = MagicMock()
        agent._emit = emit_mock

        from ds_agent.tools.path_utils import set_active_workspace

        output = tmp_path / "test.csv"
        output.write_text("a,b\n1,2", encoding="utf-8")
        set_active_workspace(tmp_path)
        try:
            agent._emit_file_created_if_applicable(
                "write_file",
                {"file_path": str(output)},
                json.dumps({"path": str(output), "success": True}),
            )
        finally:
            set_active_workspace(None)

        assert emit_mock.call_count == 2
        assert emit_mock.call_args_list[0].args[0] == "workspace.changed"
        assert emit_mock.call_args_list[1].args[0] == "file.created"
        assert emit_mock.call_args_list[1].args[1]["path"] == "test.csv"

    @pytest.mark.asyncio
    async def test_emit_file_created_for_generate_report(self, tmp_path):
        """generate_report should emit workspace + file events from output_path."""
        agent = DSAgent(provider=MagicMock(), tool_registry=MagicMock())
        emit_mock = MagicMock()
        agent._emit = emit_mock

        from ds_agent.tools.path_utils import set_active_workspace

        report = tmp_path / "report.md"
        report.write_text("# Report", encoding="utf-8")
        set_active_workspace(tmp_path)
        try:
            agent._emit_file_created_if_applicable(
                "generate_report",
                {"output_path": str(report)},
                "Report saved.",
            )
        finally:
            set_active_workspace(None)

        assert emit_mock.call_count == 2
        assert emit_mock.call_args_list[0].args[0] == "workspace.changed"
        assert emit_mock.call_args_list[1].args[0] == "file.created"
        assert emit_mock.call_args_list[1].args[1]["path"] == "report.md"

    @pytest.mark.asyncio
    async def test_emit_file_created_skips_non_file_tools(self):
        """Tools outside the file-producer/workspace-mutator sets emit nothing."""
        agent = DSAgent(provider=MagicMock(), tool_registry=MagicMock())
        emit_mock = MagicMock()
        agent._emit = emit_mock

        # ``ask_user`` is neither a file producer nor a workspace mutator.
        agent._emit_file_created_if_applicable("ask_user", {}, '{"reply": "ok"}')

        emit_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_workspace_mutating_tool_emits_refresh_only(self):
        """DS-sandbox tools (execute_code, data_loader, ...) trigger a
        workspace.changed refresh but no precise file.created event."""
        agent = DSAgent(provider=MagicMock(), tool_registry=MagicMock())
        emit_mock = MagicMock()
        agent._emit = emit_mock

        agent._emit_file_created_if_applicable(
            "data_loader", {}, '{"path": "/tmp/data.csv", "success": true}'
        )

        emit_mock.assert_called_once_with("workspace.changed", {"tool": "data_loader"})

    def test_set_callbacks_rebinds_sync_emit_bridge(self):
        """Replacing callbacks must also update hook/event emission target."""

        class CallbackA:
            def __init__(self) -> None:
                self.events: list[str] = []

            def emit_event(self, event, payload):
                self.events.append(event)

            async def on_tool_start(self, tool_name, arguments):
                return None

            async def on_tool_end(self, tool_name, result, is_error):
                return None

            async def on_thinking(self, thinking_text):
                return None

            async def on_stream_delta(self, delta):
                return None

            async def on_step(self, step_num, message):
                return None

            async def on_status(self, status, detail):
                return None

            async def on_budget_warning(self, event):
                return None

        class CallbackB(CallbackA):
            pass

        cb_a = CallbackA()
        cb_b = CallbackB()
        agent = DSAgent(provider=MagicMock(), tool_registry=MagicMock(), callbacks=cb_a)

        agent.set_callbacks(cb_b)
        agent._emit("rebuilt", {})

        assert cb_a.events == []
        assert cb_b.events == ["rebuilt"]

    @pytest.mark.asyncio
    async def test_final_response_persists_transcript(
        self, make_mock_provider, make_mock_tool_registry
    ):
        provider = make_mock_provider(
            [LLMResponse(content="Stored response", usage=Usage(input_tokens=10, output_tokens=5))]
        )

        class StubTranscriptStore:
            def __init__(self) -> None:
                self.messages: dict[str, list[ChatMessage]] = {}

            def load_messages(self, session_id: str, limit: int | None = None) -> list[ChatMessage]:
                loaded = self.messages.get(session_id, [])
                return loaded if limit is None else loaded[-limit:]

            def replace_messages(self, session_id: str, messages: list[ChatMessage]) -> None:
                self.messages[session_id] = list(messages)

        class StubCheckpointStore:
            def __init__(self) -> None:
                self.saved: dict[str, object] = {}
                self.cleared: list[str] = []

            def load(self, session_id: str):
                return None

            def save(self, checkpoint) -> None:
                self.saved[checkpoint.session_id] = checkpoint

            def clear(self, session_id: str) -> None:
                self.cleared.append(session_id)

        transcript_store = StubTranscriptStore()
        checkpoint_store = StubCheckpointStore()
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            session_id="session-1",
            transcript_store=transcript_store,
            checkpoint_store=checkpoint_store,
        )

        result = await agent.run("Persist this")

        assert result == "Stored response"
        persisted = transcript_store.messages["session-1"]
        assert [m.role for m in persisted] == [Role.USER, Role.ASSISTANT]
        assert persisted[0].content == "Persist this"
        assert persisted[1].content == "Stored response"
        assert persisted[0].message_id is not None
        assert persisted[1].message_id is not None
        assert agent.last_assistant_message_id == persisted[1].message_id
        assert "session-1" in checkpoint_store.cleared

    @pytest.mark.asyncio
    async def test_final_response_emits_cards_and_persists_stripped_message(
        self, make_mock_provider, make_mock_tool_registry
    ):
        provider = make_mock_provider(
            [
                LLMResponse(
                    content=(
                        "Summary before."
                        '<card type="insight">'
                        '{"title":"Metric up","summary":"Lifted","evidence":["auc +0.03"]}'
                        "</card>"
                        "Summary after."
                    ),
                    usage=Usage(input_tokens=10, output_tokens=5),
                )
            ]
        )

        class StubTranscriptStore:
            def __init__(self) -> None:
                self.messages: dict[str, list[ChatMessage]] = {}

            def load_messages(self, session_id: str, limit: int | None = None) -> list[ChatMessage]:
                loaded = self.messages.get(session_id, [])
                return loaded if limit is None else loaded[-limit:]

            def replace_messages(self, session_id: str, messages: list[ChatMessage]) -> None:
                self.messages[session_id] = list(messages)

        class StubCheckpointStore:
            def load(self, session_id: str):
                return None

            def save(self, checkpoint) -> None:
                return None

            def clear(self, session_id: str) -> None:
                return None

        @dataclass
        class StubEmissionResult:
            stripped_message: str
            cards: list[object]

        class StubResultCardEmitter:
            def execute(
                self,
                *,
                session_id: str,
                run_id: str,
                message_id: str,
                content: str,
                tool_call_id: str | None = None,
            ) -> StubEmissionResult:
                assert session_id == "session-cards"
                assert run_id == "run-cards"
                assert '<card type="insight">' in content
                card = coerce_result_card(
                    "insight",
                    {
                        "title": "Metric up",
                        "summary": "Lifted",
                        "evidence": ["auc +0.03"],
                    },
                    card_id="RC-1",
                    result_id="result-1",
                    created_at=datetime(2026, 4, 20, tzinfo=UTC),
                    source=ResultCardSource(messageId=message_id, runId=run_id),
                )
                return StubEmissionResult(
                    stripped_message="Summary before.Summary after.",
                    cards=[card],
                )

        transcript_store = StubTranscriptStore()
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            session_id="session-cards",
            transcript_store=transcript_store,
            checkpoint_store=StubCheckpointStore(),
            result_card_emitter=StubResultCardEmitter(),
        )
        agent.set_runtime_context("run-cards")

        result = await agent.run("Persist cards")

        assert result == "Summary before.Summary after."
        persisted = transcript_store.messages["session-cards"]
        assert persisted[-1].content == "Summary before.Summary after."
        assert agent.last_assistant_message_id == persisted[-1].message_id
        assert len(agent.last_result_cards) == 1
        assert agent.last_result_cards[0].card_id == "RC-1"
        assert agent.last_result_cards[0].result_id == "result-1"

    def test_loads_checkpoint_history_before_transcript(self, make_mock_tool_registry):
        provider = MagicMock()

        class StubTranscriptStore:
            def load_messages(self, session_id: str, limit: int | None = None) -> list[ChatMessage]:
                return [ChatMessage(role=Role.USER, content="from transcript")]

            def replace_messages(self, session_id: str, messages: list[ChatMessage]) -> None:
                return None

        class StubCheckpointStore:
            def load(self, session_id: str):
                from ds_agent.domain.entities.session_checkpoint import SessionCheckpoint

                return SessionCheckpoint(
                    session_id=session_id,
                    step=4,
                    messages=[ChatMessage(role=Role.USER, content="from checkpoint")],
                )

            def save(self, checkpoint) -> None:
                return None

            def clear(self, session_id: str) -> None:
                return None

        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            session_id="session-2",
            transcript_store=StubTranscriptStore(),
            checkpoint_store=StubCheckpointStore(),
        )

        assert agent.get_history()[0].content == "from checkpoint"
        assert agent._step == 4

    @pytest.mark.asyncio
    async def test_goal_and_working_memory_persist_after_completion(
        self, tmp_path, make_mock_provider, make_mock_tool_registry
    ):
        from ds_agent.runtime.goal_store import JsonGoalStore
        from ds_agent.runtime.working_memory import JsonWorkingMemoryStore

        provider = make_mock_provider(
            [
                LLMResponse(
                    content="Analysis complete. Report saved successfully.",
                    usage=Usage(input_tokens=10, output_tokens=5),
                )
            ]
        )

        goal_store = JsonGoalStore(base_dir=tmp_path)
        working_memory_store = JsonWorkingMemoryStore(base_dir=tmp_path)
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            session_id="session-goal-1",
            goal_store=goal_store,
            working_memory_store=working_memory_store,
        )
        agent.set_runtime_context("run-1")

        result = await agent.run("Build a churn model")

        assert "Analysis complete" in result
        goals = goal_store.list_goals("session-goal-1")
        assert len(goals) == 1
        assert goals[0].status == GoalStatus.COMPLETED
        memory = working_memory_store.load("session-goal-1")
        assert memory is not None
        assert "Report saved successfully" in memory.current_summary
        assert "follow-up goal" in memory.next_step

    @pytest.mark.asyncio
    async def test_workflow_stage_persists_into_working_memory(
        self, tmp_path, make_mock_provider, make_mock_tool_registry
    ):
        from ds_agent.runtime.goal_store import JsonGoalStore
        from ds_agent.runtime.working_memory import JsonWorkingMemoryStore

        provider = make_mock_provider(
            [
                LLMResponse(
                    tool_calls=[ToolCall(id="tc-profile", name="data_profiler", arguments={})],
                    usage=Usage(input_tokens=20, output_tokens=10),
                ),
                LLMResponse(
                    content="Profiling complete. Continue with EDA.",
                    usage=Usage(input_tokens=25, output_tokens=10),
                ),
            ]
        )

        hook_registry = HookRegistry()
        hook_registry.register(WorkflowTrackerHook())
        working_memory_store = JsonWorkingMemoryStore(base_dir=tmp_path)
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(
                {"data_profiler": lambda: "200 rows, 15 columns, missing 5.2%, Grade: B"}
            ),
            hook_registry=hook_registry,
            session_id="session-stage-1",
            goal_store=JsonGoalStore(base_dir=tmp_path),
            working_memory_store=working_memory_store,
        )
        agent.set_runtime_context("run-stage-1")

        await agent.run("Profile the dataset before modeling")

        memory = working_memory_store.load("session-stage-1")
        assert memory is not None
        assert memory.current_stage == AnalysisStage.PROFILING
        assert memory.stage_entered_at is not None

    @pytest.mark.asyncio
    async def test_session_init_stage_refreshes_first_system_prompt(
        self, tmp_path, make_mock_provider, make_mock_tool_registry
    ):
        from ds_agent.runtime.goal_store import JsonGoalStore
        from ds_agent.runtime.working_memory import JsonWorkingMemoryStore

        provider = make_mock_provider(
            [
                LLMResponse(
                    content="Mission scope captured. Ready for data loading.",
                    usage=Usage(input_tokens=20, output_tokens=10),
                )
            ]
        )
        goal_store = JsonGoalStore(base_dir=tmp_path)
        working_memory_store = JsonWorkingMemoryStore(base_dir=tmp_path)
        contract_store = MagicMock()
        contract_store.get_active_bundle.return_value = TaskContractBundle(
            contract=TaskContract(
                task_id="TC-2026-778",
                session_id="session-stage-scope-prompt",
                type="analysis",
                status=TaskContractStatus.DRAFT,
                business_goal="Clarify the churn triage request before execution.",
                required_deliverables=[
                    DeliverableSpec(type="exec_brief", audience="executive", format="md")
                ],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        hook_registry = HookRegistry()
        hook_registry.register(WorkflowTrackerHook())
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            hook_registry=hook_registry,
            prompt_builder=PromptBuilder(
                workspace_dir=str(tmp_path),
                session_id="session-stage-scope-prompt",
                task_contract_store=contract_store,
                goal_store=goal_store,
                working_memory_store=working_memory_store,
            ),
            session_id="session-stage-scope-prompt",
            goal_store=goal_store,
            working_memory_store=working_memory_store,
        )
        agent.set_runtime_context("run-stage-scope-prompt")

        await agent.run("Start the churn triage mission.")

        first_call_messages = provider.chat.await_args_list[0].kwargs["messages"]
        assert "Stage-Aware Guidance" in first_call_messages[0].content
        assert "Execution Continuity" in first_call_messages[0].content
        assert "Current stage: scoping" in first_call_messages[0].content

    @pytest.mark.asyncio
    async def test_active_task_contract_bootstraps_scoping_stage_on_session_init(
        self, tmp_path, make_mock_provider, make_mock_tool_registry
    ):
        from ds_agent.runtime.goal_store import JsonGoalStore
        from ds_agent.runtime.working_memory import JsonWorkingMemoryStore

        provider = make_mock_provider(
            [
                LLMResponse(
                    content="Mission scope captured. Ready for data loading.",
                    usage=Usage(input_tokens=20, output_tokens=10),
                )
            ]
        )
        contract_store = MagicMock()
        contract_store.get_active_bundle.return_value = TaskContractBundle(
            contract=TaskContract(
                task_id="TC-2026-777",
                session_id="session-stage-scope",
                type="analysis",
                status=TaskContractStatus.DRAFT,
                business_goal="Clarify the churn triage request before execution.",
                required_deliverables=[
                    DeliverableSpec(type="exec_brief", audience="executive", format="md")
                ],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        hook_registry = HookRegistry()
        hook_registry.register(WorkflowTrackerHook())
        working_memory_store = JsonWorkingMemoryStore(base_dir=tmp_path)
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            hook_registry=hook_registry,
            prompt_builder=PromptBuilder(
                workspace_dir=str(tmp_path),
                session_id="session-stage-scope",
                task_contract_store=contract_store,
            ),
            session_id="session-stage-scope",
            goal_store=JsonGoalStore(base_dir=tmp_path),
            working_memory_store=working_memory_store,
        )
        agent.set_runtime_context("run-stage-scope")

        await agent.run("Start the churn triage mission.")

        memory = working_memory_store.load("session-stage-scope")
        assert memory is not None
        assert memory.current_stage == AnalysisStage.SCOPING
        assert memory.stage_entered_at is not None

    @pytest.mark.asyncio
    async def test_tool_stage_refresh_preserves_session_init_injection(
        self, tmp_path, make_mock_provider, make_mock_tool_registry
    ):
        from ds_agent.runtime.goal_store import JsonGoalStore
        from ds_agent.runtime.working_memory import JsonWorkingMemoryStore

        class InitRulesHook(ToolHook):
            name = "init_rules"
            priority = 10

            async def on_session_init(self, context):
                return "## Init Rules\nAlways record assumptions before modeling."

        provider = make_mock_provider(
            [
                LLMResponse(
                    tool_calls=[ToolCall(id="tc-profile", name="data_profiler", arguments={})],
                    usage=Usage(input_tokens=20, output_tokens=10),
                ),
                LLMResponse(
                    content="Profiling complete. Continue with EDA.",
                    usage=Usage(input_tokens=25, output_tokens=10),
                ),
            ]
        )
        goal_store = JsonGoalStore(base_dir=tmp_path)
        working_memory_store = JsonWorkingMemoryStore(base_dir=tmp_path)
        hook_registry = HookRegistry()
        hook_registry.register(WorkflowTrackerHook())
        hook_registry.register(InitRulesHook())
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(
                {"data_profiler": lambda: "200 rows, 15 columns, missing 5.2%, Grade: B"}
            ),
            hook_registry=hook_registry,
            prompt_builder=PromptBuilder(
                workspace_dir=str(tmp_path),
                session_id="session-stage-refresh",
                goal_store=goal_store,
                working_memory_store=working_memory_store,
            ),
            session_id="session-stage-refresh",
            goal_store=goal_store,
            working_memory_store=working_memory_store,
        )
        agent.set_runtime_context("run-stage-refresh")

        await agent.run("Profile the dataset before modeling")

        first_call_messages = provider.chat.await_args_list[0].kwargs["messages"]
        second_call_messages = provider.chat.await_args_list[1].kwargs["messages"]

        assert "Current stage: profiling" not in first_call_messages[0].content
        assert "Init Rules" in first_call_messages[0].content
        assert "Stage-Aware Guidance" in second_call_messages[0].content
        assert "Execution Continuity" in second_call_messages[0].content
        assert "Current stage: profiling" in second_call_messages[0].content
        assert "Init Rules" in second_call_messages[0].content
        assert "Always record assumptions before modeling." in second_call_messages[0].content
        assert 'skill_view("data-profiling")' in second_call_messages[0].content

    @pytest.mark.asyncio
    async def test_goal_becomes_blocked_when_agent_requests_input(
        self, tmp_path, make_mock_provider, make_mock_tool_registry
    ):
        from ds_agent.runtime.goal_store import JsonGoalStore
        from ds_agent.runtime.working_memory import JsonWorkingMemoryStore

        provider = make_mock_provider(
            [
                LLMResponse(
                    content="Please provide the target column name?",
                    usage=Usage(input_tokens=10, output_tokens=5),
                )
            ]
        )

        goal_store = JsonGoalStore(base_dir=tmp_path)
        working_memory_store = JsonWorkingMemoryStore(base_dir=tmp_path)
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            session_id="session-goal-2",
            goal_store=goal_store,
            working_memory_store=working_memory_store,
        )
        agent.set_runtime_context("run-2")

        await agent.run("Train a classifier")

        active_goal = goal_store.get_active_goal("session-goal-2")
        assert active_goal is not None
        assert active_goal.status == GoalStatus.BLOCKED
        assert "target column" in (active_goal.blocked_reason or "")
        memory = working_memory_store.load("session-goal-2")
        assert memory is not None
        assert memory.pending_questions == ["Please provide the target column name?"]
        assert "Blocked pending clarification" in memory.last_reflection

    @pytest.mark.asyncio
    async def test_final_response_hook_marks_goal_blocked_for_followup(
        self, tmp_path, make_mock_provider, make_mock_tool_registry
    ):
        from ds_agent.runtime.goal_store import JsonGoalStore
        from ds_agent.runtime.working_memory import JsonWorkingMemoryStore

        class FollowupHook(ToolHook):
            name = "followup"
            priority = 10

            async def on_final_response(self, response, context):
                return FinalResponseResult(
                    modified_response=response + "\n\nVerifier follow-up required.",
                    requires_followup=True,
                    followup_reason="Resolve the verifier finding before review.",
                )

        provider = make_mock_provider(
            [
                LLMResponse(
                    content="Analysis complete. Report saved successfully.",
                    usage=Usage(input_tokens=10, output_tokens=5),
                )
            ]
        )

        goal_store = JsonGoalStore(base_dir=tmp_path)
        working_memory_store = JsonWorkingMemoryStore(base_dir=tmp_path)
        hook_registry = HookRegistry()
        hook_registry.register(FollowupHook())
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            hook_registry=hook_registry,
            session_id="session-goal-followup",
            goal_store=goal_store,
            working_memory_store=working_memory_store,
        )
        agent.set_runtime_context("run-followup")

        result = await agent.run("Build a churn model")

        assert "Verifier follow-up required." in result
        active_goal = goal_store.get_active_goal("session-goal-followup")
        assert active_goal is not None
        assert active_goal.status == GoalStatus.BLOCKED
        assert active_goal.blocked_reason == "Resolve the verifier finding before review."
        memory = working_memory_store.load("session-goal-followup")
        assert memory is not None
        assert memory.pending_questions == ["Resolve the verifier finding before review."]
        assert (
            memory.next_step
            == "Address the required follow-up items before moving the task to review."
        )

    @pytest.mark.asyncio
    async def test_session_outcome_is_sent_to_post_learner(
        self, tmp_path, make_mock_provider, make_mock_tool_registry
    ):
        from ds_agent.runtime.goal_store import JsonGoalStore
        from ds_agent.runtime.working_memory import JsonWorkingMemoryStore

        provider = make_mock_provider(
            [
                LLMResponse(
                    content="Analysis complete. Report saved successfully.",
                    usage=Usage(input_tokens=10, output_tokens=5),
                )
            ]
        )

        post_learner = MagicMock()
        goal_store = JsonGoalStore(base_dir=tmp_path)
        working_memory_store = JsonWorkingMemoryStore(base_dir=tmp_path)
        agent = DSAgent(
            provider=provider,
            tool_registry=make_mock_tool_registry(),
            session_id="session-goal-3",
            goal_store=goal_store,
            working_memory_store=working_memory_store,
            post_learner=post_learner,
        )
        agent.set_runtime_context("run-3")

        await agent.run("Build a classifier")

        post_learner.learn_from_session_outcome.assert_called_once()
        args = post_learner.learn_from_session_outcome.call_args[0]
        assert args[0] == "session-goal-3"
        assert args[1]["goal_status"] == "completed"
        memory = working_memory_store.load("session-goal-3")
        assert memory is not None
        assert "Completed the current goal" in memory.last_reflection


class TestWorkflowTrackerRestore:
    """GAP-3-1: WorkflowTrackerHook.restore() is called after on_session_init reset."""

    @pytest.mark.asyncio
    async def test_restore_is_called_with_persisted_stage(
        self, make_mock_provider, make_mock_tool_registry
    ):
        """After run_session_init (which calls reset()), restore() propagates
        the working memory stage back into WorkflowTrackerHook."""
        from unittest.mock import patch

        from ds_agent.domain.entities.working_memory import SessionWorkingMemory

        provider = make_mock_provider(
            [LLMResponse(content="Done.", usage=Usage(input_tokens=10, output_tokens=5))]
        )

        class StubWorkingMemoryStore:
            def __init__(self) -> None:
                self._memory = SessionWorkingMemory(
                    session_id="session-restore",
                    current_stage=AnalysisStage.PROFILING,
                )

            def load(self, session_id: str):
                return self._memory

            def save(self, memory) -> None:
                self._memory = memory

        tracker = WorkflowTrackerHook()
        hook_registry = HookRegistry()
        hook_registry.register(tracker)

        with patch.object(tracker, "restore", wraps=tracker.restore) as mock_restore:
            agent = DSAgent(
                provider=provider,
                tool_registry=make_mock_tool_registry(),
                hook_registry=hook_registry,
                session_id="session-restore",
                working_memory_store=StubWorkingMemoryStore(),
            )
            await agent.run("Continue the analysis")

        mock_restore.assert_called_once_with(
            current_stage_id=AnalysisStage.PROFILING.value
        )

    @pytest.mark.asyncio
    async def test_restore_not_called_when_no_working_memory(
        self, make_mock_provider, make_mock_tool_registry
    ):
        """restore() is a no-op when working memory is absent (new session)."""
        from unittest.mock import patch

        provider = make_mock_provider(
            [LLMResponse(content="Done.", usage=Usage(input_tokens=10, output_tokens=5))]
        )

        class EmptyWorkingMemoryStore:
            def load(self, session_id: str):
                return None

            def save(self, memory) -> None:
                pass

        tracker = WorkflowTrackerHook()
        hook_registry = HookRegistry()
        hook_registry.register(tracker)

        with patch.object(tracker, "restore", wraps=tracker.restore) as mock_restore:
            agent = DSAgent(
                provider=provider,
                tool_registry=make_mock_tool_registry(),
                hook_registry=hook_registry,
                session_id="session-no-memory",
                working_memory_store=EmptyWorkingMemoryStore(),
            )
            await agent.run("Start fresh")

        mock_restore.assert_not_called()

    @pytest.mark.asyncio
    async def test_restore_not_called_when_stage_is_none(
        self, make_mock_provider, make_mock_tool_registry
    ):
        """restore() is a no-op when working memory has no stage set."""
        from unittest.mock import patch

        from ds_agent.domain.entities.working_memory import SessionWorkingMemory

        provider = make_mock_provider(
            [LLMResponse(content="Done.", usage=Usage(input_tokens=10, output_tokens=5))]
        )

        class NoStageWorkingMemoryStore:
            def load(self, session_id: str):
                return SessionWorkingMemory(session_id=session_id, current_stage=None)

            def save(self, memory) -> None:
                pass

        tracker = WorkflowTrackerHook()
        hook_registry = HookRegistry()
        hook_registry.register(tracker)

        with patch.object(tracker, "restore", wraps=tracker.restore) as mock_restore:
            agent = DSAgent(
                provider=provider,
                tool_registry=make_mock_tool_registry(),
                hook_registry=hook_registry,
                session_id="session-no-stage",
                working_memory_store=NoStageWorkingMemoryStore(),
            )
            await agent.run("Start fresh")

        mock_restore.assert_not_called()

    def test_restore_updates_current_stage_id_in_tracker(self):
        """Unit test: restore() sets _current_stage_id on the tracker directly."""
        tracker = WorkflowTrackerHook()
        assert tracker.current_stage_id() is None

        tracker.restore(current_stage_id=AnalysisStage.MODELING.value)

        assert tracker.current_stage_id() == AnalysisStage.MODELING.value

    def test_restore_survives_unknown_stage(self):
        """restore() silently ignores unknown stage ids (defensive)."""
        tracker = WorkflowTrackerHook()
        tracker.restore(current_stage_id="nonexistent_stage")
        assert tracker.current_stage_id() is None


class TestIsToolError:
    """SEC: _is_tool_error detects all standard error formats."""

    def test_json_error_key_detected(self):
        result = json.dumps({"error": "Something went wrong", "tool": "train_model"})
        assert DSAgent._is_tool_error(result) is True

    def test_security_check_failed(self):
        assert DSAgent._is_tool_error("Security check failed: os.system()") is True

    def test_denied_result(self):
        assert DSAgent._is_tool_error("[DENIED] blocked by test") is True

    def test_success_result_not_flagged(self):
        assert DSAgent._is_tool_error("Model training completed.") is False

    def test_json_success_not_flagged(self):
        result = json.dumps({"result": "ok", "rows": 1000})
        assert DSAgent._is_tool_error(result) is False

    def test_plain_text_with_error_word_not_flagged(self):
        """'error' in text but not in JSON error key → not flagged (no false positive)."""
        assert DSAgent._is_tool_error("No errors found in dataset.") is False

    def test_old_format_plain_text_error_not_detected(self):
        """Old plain-text 'Model training error:' is NOT detected without JSON wrapping.
        This confirms the migration — tools MUST return JSON errors now."""
        assert DSAgent._is_tool_error("Model training error:\nboom") is False
