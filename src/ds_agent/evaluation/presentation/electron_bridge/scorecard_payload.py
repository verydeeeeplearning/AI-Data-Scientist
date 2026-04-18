"""Serialize scored eval runs into Electron-friendly scorecard payloads."""
# mypy: disable-error-code="no-untyped-def"


from __future__ import annotations

from typing import Any

from ds_agent.evaluation.application.dtos.eval_report_dto import ScoredRunReport
from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.entities.review_sampling import ReviewSamplingDecision
from ds_agent.evaluation.domain.entities.shadow_comparison import ShadowComparisonRecord


def build_run_scorecard_payload(
    *,
    report: ScoredRunReport,
    run: EvalRun,
    task: GoldTask,
    review_sampling: ReviewSamplingDecision | None = None,
    shadow_comparison: ShadowComparisonRecord | None = None,
) -> dict[str, Any]:
    """Return a compact scorecard payload for runtime/Electron surfaces."""

    dimensions = []
    ordered_names = list(task.scoring_rubric)
    ordered_names.extend(
        sorted(name for name in report.scores if name not in task.scoring_rubric)
    )
    for name in ordered_names:
        score = report.scores.get(name)
        if score is None:
            continue
        rubric_entry = task.scoring_rubric.get(name)
        weight = 0.0 if rubric_entry is None else rubric_entry.weight
        dimensions.append(
            {
                "name": name,
                "label": _titleize(name),
                "value": score.value,
                "weight": weight,
                "weightedContribution": weight * score.value,
                "judgeType": _enum_value(score.judge_type),
                "rubricJudge": (
                    None if rubric_entry is None else _enum_value(rubric_entry.judge)
                ),
                "rationale": score.rationale,
                "subScores": dict(score.sub_scores),
                "evidenceRefs": list(score.evidence_refs),
            }
        )

    return {
        "runId": report.run_id,
        "sessionId": report.session_id,
        "taskId": report.task_id,
        "mode": report.mode,
        "domain": task.domain,
        "difficulty": task.difficulty,
        "tags": list(task.tags),
        "weightedScore": report.weighted_score,
        "passed": report.passed,
        "passThreshold": task.pass_threshold,
        "alertOnDropBelow": task.alert_on_drop_below,
        "costUsd": report.cost_usd,
        "decisionLatencySeconds": report.decision_latency_seconds,
        "metricChoices": list(report.metric_choices),
        "artifactTypes": list(report.artifact_types),
        "toolCallCount": len(run.tool_calls),
        "approvalCount": len(run.approvals),
        "artifactCount": len(run.artifacts),
        "timingSource": report.run_metadata.get("timingSource"),
        "surface": report.run_metadata.get("surface"),
        "runtimeStatus": report.run_metadata.get("runtimeStatus"),
        "recoveryContext": _compact_mapping(
            {
                "checkpointStep": report.run_metadata.get("checkpointStep"),
                "goalStatus": report.run_metadata.get("goalStatus"),
                "goalBlockedReason": report.run_metadata.get("goalBlockedReason"),
                "taskStatus": report.run_metadata.get("taskStatus"),
            }
        ),
        "humanRubric": (
            None
            if run.human_rubric is None
            else {
                "reviewerId": run.human_rubric.reviewer_id,
                "comment": run.human_rubric.comment,
                "recordedAt": report.run_metadata.get("humanRubricRecordedAt"),
                "dimensions": dict(run.human_rubric.dimensions),
            }
        ),
        "reviewSampling": (
            None
            if review_sampling is None
            else _build_review_sampling_summary(review_sampling, run)
        ),
        "shadowComparison": (
            None
            if shadow_comparison is None
            else _build_shadow_comparison_summary(shadow_comparison)
        ),
        "dimensions": dimensions,
    }


def _titleize(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("_"))


def _compact_mapping(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in values.items()
        if value is not None and value != "" and value != () and value != [] and value != {}
    }


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _build_shadow_comparison_summary(record: ShadowComparisonRecord) -> dict[str, Any]:
    improvements = [
        _build_dimension_delta_payload(item)
        for item in record.dimension_deltas
        if item.delta > 0
    ][:3]
    regressions = [
        _build_dimension_delta_payload(item)
        for item in record.dimension_deltas
        if item.delta < 0
    ][:3]
    return {
        "comparisonId": record.comparison_id,
        "createdAt": record.created_at,
        "shadowRunId": record.shadow_run_id,
        "shadowModel": record.shadow_model,
        "shadowBudgetFactor": record.shadow_budget_factor,
        "baselineWeightedScore": record.baseline_weighted_score,
        "shadowWeightedScore": record.shadow_weighted_score,
        "weightedScoreDelta": record.weighted_score_delta,
        "baselinePassed": record.baseline_passed,
        "shadowPassed": record.shadow_passed,
        "topImprovements": improvements,
        "topRegressions": regressions,
    }


def _build_dimension_delta_payload(item) -> dict[str, Any]:
    return {
        "name": item.name,
        "label": _titleize(item.name),
        "delta": item.delta,
        "baselineValue": item.baseline_value,
        "shadowValue": item.shadow_value,
    }


def _build_review_sampling_summary(
    record: ReviewSamplingDecision,
    run: EvalRun,
) -> dict[str, Any]:
    has_human_rubric = run.human_rubric is not None
    if has_human_rubric:
        status = "completed"
    elif record.sampled:
        status = "requested"
    else:
        status = "optional"
    return {
        "sampled": record.sampled,
        "status": status,
        "targetRate": record.target_rate,
        "bucket": record.bucket,
        "stratum": record.stratum,
        "policyVersion": record.policy_version,
        "recordedAt": record.recorded_at,
        "hasHumanRubric": has_human_rubric,
    }
