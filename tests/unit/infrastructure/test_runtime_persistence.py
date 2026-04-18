"""Tests for transcript/checkpoint runtime persistence stores."""

from __future__ import annotations

import asyncio

from ds_agent.domain.entities.messages import ChatMessage, Role, ToolCall
from ds_agent.domain.entities.session_checkpoint import SessionCheckpoint
from ds_agent.domain.entities.working_memory import SessionWorkingMemory
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.checkpoint_store import JsonCheckpointStore
from ds_agent.runtime.goal_store import JsonGoalStore
from ds_agent.runtime.runtime_event_log import RuntimeEventLog
from ds_agent.runtime.task_ledger import TaskLedger
from ds_agent.runtime.transcript_store import JsonTranscriptStore
from ds_agent.runtime.working_memory import JsonWorkingMemoryStore


class TestJsonTranscriptStore:
    def test_replace_and_load_messages_roundtrip(self, tmp_path):
        store = JsonTranscriptStore(base_dir=tmp_path)
        messages = [
            ChatMessage(role=Role.USER, content="Hello"),
            ChatMessage(
                role=Role.ASSISTANT,
                content="Calling tool",
                tool_calls=[ToolCall(id="tc1", name="load_data", arguments={"path": "data.csv"})],
            ),
            ChatMessage(
                role=Role.TOOL, content='{"rows": 100}', tool_call_id="tc1", name="load_data"
            ),
        ]

        store.replace_messages("session:1", messages)
        loaded = store.load_messages("session:1")

        assert len(loaded) == 3
        assert loaded[0].role == Role.USER
        assert loaded[1].tool_calls is not None
        assert loaded[1].tool_calls[0].name == "load_data"
        assert loaded[2].tool_call_id == "tc1"

    def test_load_messages_limit_returns_tail(self, tmp_path):
        store = JsonTranscriptStore(base_dir=tmp_path)
        store.replace_messages(
            "session-2",
            [
                ChatMessage(role=Role.USER, content="one"),
                ChatMessage(role=Role.ASSISTANT, content="two"),
                ChatMessage(role=Role.USER, content="three"),
            ],
        )

        loaded = store.load_messages("session-2", limit=2)

        assert [msg.content for msg in loaded] == ["two", "three"]

    def test_thread_session_load_falls_back_to_legacy_chat_scope(self, tmp_path):
        store = JsonTranscriptStore(base_dir=tmp_path)
        store.replace_messages(
            "telegram:chat1",
            [
                ChatMessage(role=Role.USER, content="legacy ask"),
                ChatMessage(role=Role.ASSISTANT, content="legacy answer"),
            ],
        )

        loaded = store.load_messages("telegram:chat1:77")

        assert [msg.content for msg in loaded] == ["legacy ask", "legacy answer"]

    def test_thread_session_prefers_exact_transcript_over_legacy(self, tmp_path):
        store = JsonTranscriptStore(base_dir=tmp_path)
        store.replace_messages("telegram:chat1", [ChatMessage(role=Role.USER, content="legacy")])
        store.replace_messages(
            "telegram:chat1:77",
            [ChatMessage(role=Role.USER, content="topic specific")],
        )

        loaded = store.load_messages("telegram:chat1:77")

        assert [msg.content for msg in loaded] == ["topic specific"]


class TestJsonCheckpointStore:
    def test_save_load_and_clear_checkpoint(self, tmp_path):
        store = JsonCheckpointStore(base_dir=tmp_path)
        checkpoint = SessionCheckpoint(
            session_id="telegram:chat-1",
            step=3,
            messages=[
                ChatMessage(role=Role.USER, content="Continue analysis"),
                ChatMessage(role=Role.ASSISTANT, content="Thinking"),
            ],
            updated_at=123.0,
        )

        store.save(checkpoint)
        loaded = store.load("telegram:chat-1")

        assert loaded is not None
        assert loaded.step == 3
        assert len(loaded.messages) == 2

        store.clear("telegram:chat-1")
        assert store.load("telegram:chat-1") is None

    def test_thread_session_load_falls_back_to_legacy_chat_scope(self, tmp_path):
        store = JsonCheckpointStore(base_dir=tmp_path)
        legacy = SessionCheckpoint(
            session_id="telegram:chat-1",
            step=7,
            messages=[ChatMessage(role=Role.USER, content="legacy checkpoint")],
            updated_at=321.0,
        )
        store.save(legacy)

        loaded = store.load("telegram:chat-1:55")

        assert loaded is not None
        assert loaded.step == 7
        assert loaded.messages[0].content == "legacy checkpoint"


class TestJsonApprovalStore:
    def test_thread_session_list_falls_back_to_legacy_chat_scope(self, tmp_path):
        store = JsonApprovalStore(base_dir=tmp_path)
        legacy = store.create(
            session_id="telegram:chat1",
            run_id="run-1",
            surface="telegram",
            question="Use legacy approval?",
        )

        pending = store.list(session_id="telegram:chat1:77", status=legacy.status, limit=5)

        assert [item.approval_id for item in pending] == [legacy.approval_id]

    def test_thread_session_list_does_not_fallback_when_exact_topic_exists(self, tmp_path):
        store = JsonApprovalStore(base_dir=tmp_path)
        store.create(
            session_id="telegram:chat1",
            run_id="run-legacy",
            surface="telegram",
            question="Legacy approval",
        )
        exact = store.create(
            session_id="telegram:chat1:77",
            run_id="run-topic",
            surface="telegram",
            question="Topic approval",
        )

        pending = store.list(session_id="telegram:chat1:77", status=exact.status, limit=5)

        assert [item.approval_id for item in pending] == [exact.approval_id]


class TestJsonGoalStore:
    def test_thread_session_active_goal_falls_back_to_legacy_chat_scope(self, tmp_path):
        store = JsonGoalStore(base_dir=tmp_path)
        legacy = store.ensure_from_message("telegram:chat1", "Investigate churn drivers")

        goal = store.get_active_goal("telegram:chat1:77")

        assert goal is not None
        assert goal.goal_id == legacy.goal_id


class TestJsonWorkingMemoryStore:
    def test_thread_session_load_falls_back_to_legacy_chat_scope(self, tmp_path):
        store = JsonWorkingMemoryStore(base_dir=tmp_path)
        store.save(
            SessionWorkingMemory(
                session_id="telegram:chat1",
                current_summary="Legacy summary",
                next_step="Legacy next step",
                recovery_note="Legacy recovery note",
            )
        )

        memory = store.load("telegram:chat1:77")

        assert memory is not None
        assert memory.current_summary == "Legacy summary"
        assert memory.next_step == "Legacy next step"


class TestRuntimeEventLog:
    def test_record_and_list_roundtrip_across_instances(self, tmp_path):
        writer = RuntimeEventLog(base_dir=tmp_path)
        event = writer.record(
            category="recovery",
            kind="recovery.resume_recommended",
            severity="info",
            message="Recovered session can resume.",
            session_id="telegram:chat-1",
            run_id="run-9",
            surface="daemon",
            source="startup_recovery",
        )

        reader = RuntimeEventLog(base_dir=tmp_path)
        events = reader.list(limit=5)

        assert len(events) == 1
        assert events[0].kind == "recovery.resume_recommended"
        assert events[0].session_id == "telegram:chat-1"
        assert events[0].run_id == "run-9"
        assert reader.get(event.event_id) is not None

    def test_list_returns_newest_first(self, tmp_path):
        log = RuntimeEventLog(base_dir=tmp_path)
        log.record(
            category="pressure",
            kind="system.resource.pressure",
            severity="warning",
            message="Pressure on.",
            created_at=10.0,
        )
        log.record(
            category="pressure",
            kind="system.resource.normal",
            severity="success",
            message="Pressure cleared.",
            created_at=20.0,
        )

        events = log.list(limit=2)

        assert [event.kind for event in events] == [
            "system.resource.normal",
            "system.resource.pressure",
        ]


class TestTaskLedger:
    async def test_task_state_roundtrip_across_instances(self, tmp_path):
        writer = TaskLedger(base_dir=tmp_path)
        task = asyncio.create_task(asyncio.sleep(0.01))

        state = writer.register("run-123", task)
        await writer.wait_for_run("run-123", timeout_seconds=1.0)

        reader = TaskLedger(base_dir=tmp_path)
        restored = reader.get_state(state.task_id)

        assert restored is not None
        assert restored.run_id == "run-123"
        assert restored.status.value == "succeeded"
        assert restored.finished_at is not None
        assert reader.get_state_for_run("run-123") is not None
        assert reader.active_count == 0
