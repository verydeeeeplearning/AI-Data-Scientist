from __future__ import annotations

from ds_agent.evaluation.application.dtos.eval_report_dto import ScoredRunReport
from ds_agent.evaluation.domain.entities.eval_run import (
    EvalApprovalDecision,
    EvalArtifact,
    EvalRun,
    EvalToolCall,
)
from ds_agent.evaluation.domain.entities.eval_score import EvalScore
from ds_agent.evaluation.domain.entities.human_rubric import HumanRubric
from ds_agent.evaluation.domain.entities.review_sampling import ReviewSamplingDecision
from ds_agent.evaluation.domain.entities.shadow_comparison import ShadowComparisonRecord
from ds_agent.evaluation.infrastructure.adapters.production_task_adapter import (
    ProductionTaskAdapter,
)
from ds_agent.evaluation.presentation.electron_bridge.scorecard_payload import (
    build_run_scorecard_payload,
)


def test_build_run_scorecard_payload_preserves_recovery_context() -> None:
    task = ProductionTaskAdapter().from_session(
        session_id="session-1",
        prompt="Evaluate production session session-1.",
        task_id="task-1",
    )
    run = EvalRun(
        run_id="run-1",
        session_id="session-1",
        task_id="task-1",
        mode="online",
        user_prompt="Investigate churn increase.",
        started_at=10.0,
        finished_at=40.0,
        decision_ready_at=25.0,
        cost_usd=1.75,
        tool_calls=(EvalToolCall(name="data_loader"),),
        approvals=(EvalApprovalDecision(action="export_results", approved=True),),
        artifacts=(
            EvalArtifact(artifact_type="executive_summary", content="Summary"),
            EvalArtifact(artifact_type="goal_state", content="blocked"),
        ),
        metadata={
            "timingSource": "runtime_event_log",
            "surface": "desktop",
            "runtimeStatus": "succeeded",
            "checkpointStep": "resume:feature-selection",
            "goalStatus": "blocked",
            "goalBlockedReason": "awaiting operator confirmation",
            "taskStatus": "running",
            "humanRubricRecordedAt": 55.0,
        },
        human_rubric=HumanRubric(
            reviewer_id="reviewer-1",
            dimensions={"operator_satisfaction": 0.82},
            comment="Recovered well once the operator replied.",
        ),
    )
    report = ScoredRunReport(
        task_id="task-1",
        run_id="run-1",
        mode="online",
        weighted_score=0.74,
        passed=True,
        session_id="session-1",
        cost_usd=1.75,
        decision_latency_seconds=15.0,
        metric_choices=("roc_auc",),
        artifact_types=("executive_summary", "goal_state"),
        run_metadata=dict(run.metadata),
        scores={
            "operator_satisfaction": EvalScore.model_validate(
                {
                    "name": "operator_satisfaction",
                    "value": 0.8,
                    "rationale": "Recovered from a blocked state and resumed cleanly.",
                    "sub_scores": {
                        "follow_up_signal": 0.9,
                        "recovery_continuity": 0.8,
                    },
                    "judge_type": task.scoring_rubric["operator_satisfaction"].judge,
                }
            ),
            "time_to_decision": EvalScore.model_validate(
                {
                    "name": "time_to_decision",
                    "value": 0.6,
                    "rationale": "Decision surfaced in 15 seconds.",
                    "judge_type": task.scoring_rubric["time_to_decision"].judge,
                }
            ),
        },
    )

    payload = build_run_scorecard_payload(report=report, run=run, task=task)

    assert payload["runId"] == "run-1"
    assert payload["weightedScore"] == 0.74
    assert payload["decisionLatencySeconds"] == 15.0
    assert payload["recoveryContext"] == {
        "checkpointStep": "resume:feature-selection",
        "goalStatus": "blocked",
        "goalBlockedReason": "awaiting operator confirmation",
        "taskStatus": "running",
    }
    assert payload["humanRubric"] == {
        "reviewerId": "reviewer-1",
        "comment": "Recovered well once the operator replied.",
        "recordedAt": 55.0,
        "dimensions": {"operator_satisfaction": 0.82},
    }
    assert payload["toolCallCount"] == 1
    assert payload["approvalCount"] == 1

    dimensions = {item["name"]: item for item in payload["dimensions"]}
    assert dimensions["operator_satisfaction"]["label"] == "Operator Satisfaction"
    assert dimensions["operator_satisfaction"]["judgeType"] == "human_or_proxy"
    assert dimensions["operator_satisfaction"]["subScores"]["recovery_continuity"] == 0.8
    assert dimensions["time_to_decision"]["weightedContribution"] > 0.0


def test_build_run_scorecard_payload_includes_latest_shadow_summary() -> None:
    task = ProductionTaskAdapter().from_session(
        session_id="session-1",
        prompt="Evaluate production session session-1.",
        task_id="task-1",
    )
    run = EvalRun(
        run_id="run-1",
        session_id="session-1",
        task_id="task-1",
        mode="online",
        started_at=10.0,
        finished_at=40.0,
        decision_ready_at=25.0,
        metadata={"model": "anthropic/claude-sonnet-4-6"},
    )
    report = ScoredRunReport(
        task_id="task-1",
        run_id="run-1",
        mode="online",
        weighted_score=0.74,
        passed=True,
        session_id="session-1",
        run_metadata=dict(run.metadata),
        scores={
            "operator_satisfaction": EvalScore.model_validate(
                {
                    "name": "operator_satisfaction",
                    "value": 0.8,
                    "rationale": "Recovered well once the operator replied.",
                    "judge_type": task.scoring_rubric["operator_satisfaction"].judge,
                }
            ),
        },
    )
    shadow_comparison = ShadowComparisonRecord(
        session_id="session-1",
        task_id="task-1",
        baseline_run_id="run-1",
        shadow_run_id="shadow-run-1",
        baseline_weighted_score=0.74,
        shadow_weighted_score=0.81,
        weighted_score_delta=0.07,
        baseline_passed=True,
        shadow_passed=True,
        baseline_scores=report.scores,
        shadow_scores=report.scores,
        shadow_model="openai/gpt-4.1-mini",
        dimension_deltas=(),
    )

    payload = build_run_scorecard_payload(
        report=report,
        run=run,
        task=task,
        shadow_comparison=shadow_comparison,
    )

    assert payload["shadowComparison"] == {
        "comparisonId": shadow_comparison.comparison_id,
        "createdAt": shadow_comparison.created_at,
        "shadowRunId": "shadow-run-1",
        "shadowModel": "openai/gpt-4.1-mini",
        "shadowBudgetFactor": 0.5,
        "baselineWeightedScore": 0.74,
        "shadowWeightedScore": 0.81,
        "weightedScoreDelta": 0.07,
        "baselinePassed": True,
        "shadowPassed": True,
        "topImprovements": [],
        "topRegressions": [],
    }


def test_build_run_scorecard_payload_includes_review_sampling_summary() -> None:
    task = ProductionTaskAdapter().from_session(
        session_id="session-1",
        prompt="Evaluate production session session-1.",
        task_id="task-1",
    )
    run = EvalRun(
        run_id="run-1",
        session_id="session-1",
        task_id="task-1",
        mode="online",
        started_at=10.0,
        finished_at=40.0,
        decision_ready_at=25.0,
        human_rubric=HumanRubric(
            reviewer_id="reviewer-1",
            dimensions={"operator_satisfaction": 0.82},
        ),
    )
    report = ScoredRunReport(
        task_id="task-1",
        run_id="run-1",
        mode="online",
        weighted_score=0.74,
        passed=True,
        session_id="session-1",
        scores={
            "operator_satisfaction": EvalScore.model_validate(
                {
                    "name": "operator_satisfaction",
                    "value": 0.8,
                    "rationale": "Recovered well once the operator replied.",
                    "judge_type": task.scoring_rubric["operator_satisfaction"].judge,
                }
            ),
        },
    )
    review_sampling = ReviewSamplingDecision(
        session_id="session-1",
        run_id="run-1",
        task_id="task-1",
        domain="generic",
        surface="ws",
        target_rate=0.2,
        bucket=0.12,
        sampled=True,
        stratum="domain:generic",
    )

    payload = build_run_scorecard_payload(
        report=report,
        run=run,
        task=task,
        review_sampling=review_sampling,
    )

    assert payload["reviewSampling"] == {
        "sampled": True,
        "status": "completed",
        "targetRate": 0.2,
        "bucket": 0.12,
        "stratum": "domain:generic",
        "policyVersion": "domain_hash_v1",
        "recordedAt": review_sampling.recorded_at,
        "hasHumanRubric": True,
    }
