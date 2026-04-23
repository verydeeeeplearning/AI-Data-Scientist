"""Tests for goal store and working memory runtime persistence."""

from __future__ import annotations

from ds_agent.domain.entities.goal import GoalStatus
from ds_agent.domain.entities.working_memory import SessionWorkingMemory
from ds_agent.domain.value_objects.analysis_stage import AnalysisStage
from ds_agent.runtime.goal_store import JsonGoalStore
from ds_agent.runtime.working_memory import JsonWorkingMemoryStore


class TestJsonGoalStore:
    def test_ensure_goal_and_restore_active_goal(self, tmp_path):
        store = JsonGoalStore(base_dir=tmp_path)

        created = store.ensure_from_message("session-1", "Build a churn model", run_id="run-1")
        restored = JsonGoalStore(base_dir=tmp_path).get_active_goal("session-1")

        assert created.goal_id == restored.goal_id
        assert restored.status == GoalStatus.PENDING
        assert restored.last_run_id == "run-1"

    def test_mark_status_persists_terminal_state(self, tmp_path):
        store = JsonGoalStore(base_dir=tmp_path)
        goal = store.ensure_from_message("session-1", "Build a churn model")

        store.mark_status(
            "session-1",
            goal.goal_id,
            GoalStatus.COMPLETED,
            run_id="run-2",
            note="Model and report completed.",
        )

        listed = JsonGoalStore(base_dir=tmp_path).list_goals("session-1")
        assert listed[0].status == GoalStatus.COMPLETED
        assert listed[0].last_run_id == "run-2"
        assert "Model and report completed." in listed[0].notes
        assert JsonGoalStore(base_dir=tmp_path).get_active_goal("session-1") is None

    def test_blocked_goal_remains_active(self, tmp_path):
        store = JsonGoalStore(base_dir=tmp_path)
        goal = store.ensure_from_message("session-1", "Analyze the dataset")

        store.mark_status(
            "session-1",
            goal.goal_id,
            GoalStatus.BLOCKED,
            blocked_reason="Need the target column.",
        )

        active = store.get_active_goal("session-1")
        assert active is not None
        assert active.status == GoalStatus.BLOCKED
        assert active.blocked_reason == "Need the target column."


class TestJsonWorkingMemoryStore:
    def test_save_and_load(self, tmp_path):
        store = JsonWorkingMemoryStore(base_dir=tmp_path)
        memory = SessionWorkingMemory(
            session_id="session-1",
            active_goal_id="goal-1",
            last_run_id="run-1",
            last_user_message="Analyze the dataset",
            current_summary="Loaded the data and profiled missing values.",
            next_step="Train a baseline model.",
            pending_questions=["Which target column should be used?"],
            last_reflection="Blocked pending clarification.",
            recovery_note="Recovered after restart from checkpoint step 2.",
            current_stage=AnalysisStage.PROFILING,
            stage_entered_at=123.45,
        )

        store.save(memory)
        loaded = JsonWorkingMemoryStore(base_dir=tmp_path).load("session-1")

        assert loaded is not None
        assert loaded.active_goal_id == "goal-1"
        assert loaded.current_summary.startswith("Loaded the data")
        assert loaded.pending_questions == ["Which target column should be used?"]
        assert loaded.last_reflection == "Blocked pending clarification."
        assert loaded.recovery_note == "Recovered after restart from checkpoint step 2."
        assert loaded.current_stage == AnalysisStage.PROFILING
        assert loaded.stage_entered_at == 123.45
