"""Tests for structured session outcome building."""

from ds_agent.self_improve.outcome_builder import build_session_outcome


class TestBuildSessionOutcome:
    def test_completed_goal_maps_to_successful_outcome(self):
        outcome = build_session_outcome(
            session_id="session-1",
            final_output="Analysis complete. Report saved successfully.",
            goal_summary="Train a classifier",
            goal_status="completed",
            blocked_reason=None,
            pending_questions=[],
            current_summary="Built and evaluated the final model.",
            next_step="Start a follow-up goal only if requested.",
            reflection="Completed the current goal.",
            model_name="anthropic/claude-sonnet-4-6",
            total_cost_usd=0.42,
            duration_seconds=12.5,
            iterations=4,
        )

        assert outcome.success is True
        assert outcome.primary_metric == "goal_completion"
        assert outcome.primary_metric_value == 1.0
        assert outcome.best_model == "anthropic/claude-sonnet-4-6"
        assert outcome.task_type == "classification"

    def test_blocked_goal_maps_to_failure_reason(self):
        outcome = build_session_outcome(
            session_id="session-2",
            final_output="Please provide the target column name?",
            goal_summary="Explore the dataset",
            goal_status="blocked",
            blocked_reason="Need the target column.",
            pending_questions=["Please provide the target column name?"],
            current_summary="Profiled the dataset and found missing target semantics.",
            next_step="Wait for user input.",
            reflection="Blocked pending clarification.",
            model_name="openai/gpt-5.4",
            total_cost_usd=0.1,
            duration_seconds=3.0,
            iterations=2,
        )

        assert outcome.success is False
        assert outcome.primary_metric_value == 0.0
        assert outcome.failure_reason == "Need the target column."
        assert outcome.task_type == "eda"
