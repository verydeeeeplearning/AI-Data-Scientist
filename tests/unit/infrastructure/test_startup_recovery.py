"""Tests for startup recovery and orphan reconciliation."""

from __future__ import annotations

from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.entities.session_checkpoint import SessionCheckpoint
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.checkpoint_store import JsonCheckpointStore
from ds_agent.runtime.goal_store import JsonGoalStore
from ds_agent.runtime.sensor_hub import SensorHub
from ds_agent.runtime.startup_recovery import StartupRecovery
from ds_agent.runtime.working_memory import JsonWorkingMemoryStore


class TestStartupRecovery:
    def test_resume_recommended_session_publishes_recovery_event(self, tmp_path):
        checkpoint_store = JsonCheckpointStore(base_dir=tmp_path)
        goal_store = JsonGoalStore(base_dir=tmp_path)
        working_memory_store = JsonWorkingMemoryStore(base_dir=tmp_path)
        approval_store = JsonApprovalStore(base_dir=tmp_path)
        sensor_hub = SensorHub()

        checkpoint_store.save(
            SessionCheckpoint(
                session_id="session-1",
                step=5,
                messages=[ChatMessage(role=Role.USER, content="Continue")],
            )
        )
        goal_store.ensure_from_message("session-1", "Train a churn classifier", run_id="run-1")

        recovery = StartupRecovery(
            checkpoint_store=checkpoint_store,
            goal_store=goal_store,
            working_memory_store=working_memory_store,
            approval_store=approval_store,
            sensor_hub=sensor_hub,
        )

        records = recovery.recover()
        event = sensor_hub.publish(
            sensor="test",
            kind="noop",
            session_id="noop",
            surface="test",
            message="noop",
        )
        _ = event  # keep queue non-empty only after recovery call

        assert len(records) == 1
        assert records[0].action == "resume_recommended"
        memory = working_memory_store.load("session-1")
        assert memory is not None
        assert "Recovered after restart" in (memory.recovery_note or "")
        assert "Resume from the recovered checkpoint" in memory.next_step

        recovered_event = sensor_hub._queue.get_nowait()
        assert recovered_event.kind == "recovery.resume"
        assert recovered_event.session_id == "session-1"

    def test_pending_approval_session_stays_blocked(self, tmp_path):
        checkpoint_store = JsonCheckpointStore(base_dir=tmp_path)
        goal_store = JsonGoalStore(base_dir=tmp_path)
        working_memory_store = JsonWorkingMemoryStore(base_dir=tmp_path)
        approval_store = JsonApprovalStore(base_dir=tmp_path)

        checkpoint_store.save(
            SessionCheckpoint(
                session_id="session-2",
                step=3,
                messages=[ChatMessage(role=Role.USER, content="Continue")],
            )
        )
        goal = goal_store.ensure_from_message("session-2", "Train a model", run_id="run-2")
        approval_store.create(
            session_id="session-2",
            run_id="run-2",
            surface="telegram",
            question="Which target column should be used?",
        )

        recovery = StartupRecovery(
            checkpoint_store=checkpoint_store,
            goal_store=goal_store,
            working_memory_store=working_memory_store,
            approval_store=approval_store,
        )
        records = recovery.recover()

        assert len(records) == 1
        assert records[0].action == "awaiting_approval"
        active_goal = goal_store.get_active_goal("session-2")
        assert active_goal is not None
        assert active_goal.goal_id == goal.goal_id
        assert active_goal.status.value == "blocked"
        memory = working_memory_store.load("session-2")
        assert memory is not None
        assert memory.pending_questions == ["Which target column should be used?"]


class TestCheckpointListing:
    def test_checkpoint_store_lists_recent_sessions(self, tmp_path):
        store = JsonCheckpointStore(base_dir=tmp_path)
        store.save(
            SessionCheckpoint(
                session_id="session-a",
                step=1,
                messages=[ChatMessage(role=Role.USER, content="a")],
                updated_at=10.0,
            )
        )
        store.save(
            SessionCheckpoint(
                session_id="session-b",
                step=2,
                messages=[ChatMessage(role=Role.USER, content="b")],
                updated_at=20.0,
            )
        )

        checkpoints = store.list(limit=10)

        assert [item.session_id for item in checkpoints] == ["session-b", "session-a"]
