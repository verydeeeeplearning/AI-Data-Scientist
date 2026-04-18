from __future__ import annotations

from ds_agent.evaluation.application.use_cases.score_run import ScoreRun
from ds_agent.evaluation.domain.entities.eval_run import (
    EvalApprovalDecision,
    EvalArtifact,
    EvalOperatorFeedback,
    EvalRun,
    EvalToolCall,
)
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.entities.human_rubric import HumanRubric
from ds_agent.evaluation.infrastructure.scorers.operator_satisfaction import (
    OperatorSatisfactionScorer,
)
from ds_agent.evaluation.infrastructure.scorers.registry import build_default_scorers


def _task() -> GoldTask:
    return GoldTask.model_validate(
        {
            "id": "retail.churn_scoping.v1",
            "task_version": 1,
            "domain": "retail",
            "difficulty": "medium",
            "prompt": "Investigate churn and prepare a campaign-ready list.",
            "input": {
                "datasets": [{"name": "subscriptions", "source": "fixtures/subscriptions.parquet"}],
                "snapshot_date": "2024-12-31",
                "budget_usd": 20.0,
                "time_budget_min": 30,
            },
            "expected_deliverables": [
                {
                    "type": "goal_brief",
                    "must_contain": [
                        "problem_framing",
                        "kpi_definition",
                        "segment_definition",
                    ],
                },
                {"type": "eda_report"},
                {"type": "model_artifact"},
                {"type": "ranked_customer_list"},
                {"type": "executive_summary"},
            ],
            "validation_points": {
                "metric_selection": {
                    "acceptable_primary": ["pr_auc", "lift_at_10pct"],
                    "forbidden_primary": ["accuracy"],
                },
                "approval_required": {
                    "sending_campaign": True,
                    "publishing_model": True,
                },
            },
            "scoring_rubric": {
                "scoping_accuracy": {"weight": 0.15, "judge": "llm"},
                "metric_selection_accuracy": {"weight": 0.10, "judge": "hybrid"},
                "temporal_leakage_detection": {"weight": 0.15, "judge": "deterministic"},
                "tool_trajectory": {"weight": 0.05, "judge": "deterministic"},
                "artifact_faithfulness": {"weight": 0.15, "judge": "llm"},
                "exec_summary_accuracy": {"weight": 0.10, "judge": "llm"},
                "approval_judgment": {"weight": 0.10, "judge": "hybrid"},
                "session_completeness": {"weight": 0.10, "judge": "hybrid"},
                "operator_satisfaction": {"weight": 0.05, "judge": "human_or_proxy"},
                "time_to_decision": {"weight": 0.05, "judge": "deterministic"},
            },
            "pass_threshold": 0.75,
            "alert_on_drop_below": 0.70,
        }
    )


def _good_run() -> EvalRun:
    return EvalRun(
        run_id="run-good",
        session_id="sess-1",
        task_id="retail.churn_scoping.v1",
        started_at=0.0,
        finished_at=20.0 * 60.0,
        decision_ready_at=18.0 * 60.0,
        cost_usd=7.5,
        goal_brief={
            "business_question": "Why did churn rise?",
            "ds_problem_statement": "Predict churn_30d and identify top drivers.",
            "decision_to_make": "Select a high-risk cohort for the next campaign.",
            "problem_framing": "Unexpected churn spike needs triage.",
            "kpi_definition": "Use PR-AUC and Lift@10%.",
            "segment_definition": "Tenure > 3 months and currently active customers.",
        },
        metric_choices=("pr_auc", "lift_at_10pct"),
        tool_calls=(
            EvalToolCall(name="load_data", arguments={"name": "subscriptions"}, cost_usd=0.5),
            EvalToolCall(name="profile_data", arguments={"dataset": "subscriptions"}, cost_usd=0.5),
            EvalToolCall(name="run_eda", arguments={"cohort": "plan"}, cost_usd=0.8),
            EvalToolCall(name="build_features", arguments={"target": "churn_30d"}, cost_usd=1.2),
            EvalToolCall(name="train_model", arguments={"algorithm": "xgboost"}, cost_usd=2.0),
            EvalToolCall(name="evaluate_model", arguments={"metric": "pr_auc"}, cost_usd=1.5),
            EvalToolCall(name="generate_report", arguments={"format": "markdown"}, cost_usd=1.0),
        ),
        approvals=(
            EvalApprovalDecision(action="sending_campaign", requested=True),
            EvalApprovalDecision(action="publishing_model", requested=True),
        ),
        artifacts=(
            EvalArtifact(
                artifact_type="goal_brief",
                content="Problem framing, KPI definition, and segment definition are complete.",
            ),
            EvalArtifact(
                artifact_type="eda_report",
                content="Plan cohorts show 17.0 vs 12.0 churn by tenure segment.",
            ),
            EvalArtifact(
                artifact_type="model_artifact",
                content="PR-AUC 0.84, lift_at_10pct 2.40.",
            ),
            EvalArtifact(
                artifact_type="ranked_customer_list",
                content="Top 500 customers ranked for campaign review.",
            ),
            EvalArtifact(
                artifact_type="executive_summary",
                content="Core finding, confidence, limitations, and recommended action included.",
            ),
        ),
        underlying_metrics={
            "pr_auc": 0.84,
            "lift_at_10pct": 2.40,
            "churn_current_pct": 17.0,
            "churn_baseline_pct": 12.0,
        },
        final_summary=(
            "Core finding: churn rose to 17.0 and PR-AUC reached 0.84. "
            "Confidence: medium-high. "
            "Limitations: no uplift labels yet and one quarter history only. "
            "Recommended action: request approval before sending campaign."
        ),
        summary_sections={
            "core_finding": "churn rose to 17.0 and PR-AUC reached 0.84",
            "confidence": "medium-high",
            "limitations": "No uplift labels yet and one quarter history only.",
            "recommended_action": "Request approval before sending campaign.",
        },
        operator_feedback=EvalOperatorFeedback(approved_final=True, follow_up_messages=0),
    )


def _bad_run() -> EvalRun:
    return EvalRun(
        run_id="run-bad",
        session_id="sess-1",
        task_id="retail.churn_scoping.v1",
        started_at=0.0,
        finished_at=70.0 * 60.0,
        decision_ready_at=65.0 * 60.0,
        cost_usd=28.0,
        goal_brief={"business_question": "Fix churn."},
        metric_choices=("accuracy",),
        temporal_violations=("used post_snapshot events",),
        tool_calls=(
            EvalToolCall(name="evaluate_model", arguments={"metric": "accuracy"}, status="error"),
            EvalToolCall(name="evaluate_model", arguments={"metric": "accuracy"}, status="error"),
            EvalToolCall(name="generate_report", arguments={"format": "markdown"}),
        ),
        approvals=(),
        artifacts=(
            EvalArtifact(
                artifact_type="executive_summary",
                content="TODO later",
            ),
        ),
        underlying_metrics={"pr_auc": 0.41},
        final_summary="Accuracy was great at 99.0. Confidence unknown. TODO.",
        summary_sections={"core_finding": "Accuracy was great."},
        operator_feedback=EvalOperatorFeedback(
            approved_final=False,
            follow_up_messages=3,
            manual_intervention=True,
        ),
        metadata={"train_test_not_time_ordered": True},
    )


def test_each_default_scorer_rewards_good_run() -> None:
    task = _task()
    good_run = _good_run()
    bad_run = _bad_run()

    for scorer in build_default_scorers():
        good_score = scorer.score(good_run, task)
        bad_score = scorer.score(bad_run, task)
        assert good_score.value > bad_score.value, scorer.name


def test_weighted_score_passes_good_run_and_fails_bad_run() -> None:
    task = _task()
    scorer = ScoreRun(build_default_scorers())

    good_report = scorer.execute(run=_good_run(), task=task)
    bad_report = scorer.execute(run=_bad_run(), task=task)

    assert good_report.passed is True
    assert bad_report.passed is False
    assert good_report.weighted_score > bad_report.weighted_score


def test_operator_satisfaction_proxy_uses_recovery_context() -> None:
    scorer = OperatorSatisfactionScorer()
    task = _task()

    recovered_completed = _good_run().model_copy(
        update={
            "metadata": {
                "goalStatus": "completed",
                "taskStatus": "succeeded",
                "checkpointStep": 4,
            }
        }
    )
    blocked_transparent = _good_run().model_copy(
        update={
            "operator_feedback": EvalOperatorFeedback(approved_final=True, follow_up_messages=1),
            "metadata": {
                "goalStatus": "blocked",
                "goalBlockedReason": "Need approval before launching the campaign.",
                "taskStatus": "succeeded",
                "checkpointStep": 4,
            },
        }
    )
    blocked_opaque = _good_run().model_copy(
        update={
            "operator_feedback": EvalOperatorFeedback(
                approved_final=False,
                follow_up_messages=2,
                manual_intervention=True,
            ),
            "metadata": {
                "goalStatus": "blocked",
                "taskStatus": "failed",
                "checkpointStep": 4,
            },
        }
    )

    recovered_score = scorer.score(recovered_completed, task)
    transparent_score = scorer.score(blocked_transparent, task)
    opaque_score = scorer.score(blocked_opaque, task)

    assert recovered_score.value > transparent_score.value > opaque_score.value
    assert transparent_score.sub_scores["recovery_continuity"] == 1.0
    assert opaque_score.sub_scores["recovery_continuity"] == 0.0


def test_score_run_honors_human_rubric_overrides() -> None:
    task = _task()
    run = _good_run().model_copy(
        update={
            "human_rubric": HumanRubric(
                reviewer_id="reviewer-1",
                dimensions={
                    "scoping_accuracy": 0.2,
                    "operator_satisfaction": 0.95,
                },
                comment="Scope framing was weak but the operator experience was strong.",
            ),
        }
    )

    report = ScoreRun(build_default_scorers()).execute(run=run, task=task)

    assert report.scores["scoping_accuracy"].value == 0.2
    assert report.scores["operator_satisfaction"].value == 0.95
    assert report.scores["scoping_accuracy"].sub_scores["auto_score"] > 0.2
    assert "Human rubric override" in report.scores["scoping_accuracy"].rationale
