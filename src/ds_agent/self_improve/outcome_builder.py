"""Build structured session outcomes for reflection and post-project learning."""

from __future__ import annotations

from ds_agent.self_improve.post_project import ProjectOutcome


def build_session_outcome(
    *,
    session_id: str,
    final_output: str,
    goal_summary: str | None,
    goal_status: str,
    blocked_reason: str | None,
    pending_questions: list[str],
    current_summary: str,
    next_step: str,
    reflection: str,
    model_name: str,
    total_cost_usd: float,
    duration_seconds: float,
    iterations: int,
) -> ProjectOutcome:
    """Translate one agent turn into a structured ``ProjectOutcome``."""
    success = goal_status == "completed"
    primary_metric_value = 1.0 if success else 0.25 if goal_status == "in_progress" else 0.0
    task_type = _infer_task_type(goal_summary, final_output)

    key_findings = [item for item in [current_summary, reflection] if item]
    if success and final_output:
        key_findings.append(final_output[:240])

    failure_reason = None
    if not success:
        failure_reason = blocked_reason or (pending_questions[0] if pending_questions else None)
        if not failure_reason:
            failure_reason = final_output[:240] if final_output else "Session did not complete."

    return ProjectOutcome(
        project_id=session_id,
        task_type=task_type,
        success=success,
        primary_metric="goal_completion",
        primary_metric_value=primary_metric_value,
        models_tried=[model_name] if model_name else [],
        best_model=model_name or None,
        key_findings=key_findings[:3],
        steps_taken=[step for step in [next_step] if step],
        failure_reason=failure_reason,
        duration_seconds=max(duration_seconds, 0.0),
        total_cost_usd=max(total_cost_usd, 0.0),
    )


def _infer_task_type(goal_summary: str | None, final_output: str) -> str:
    text = f"{goal_summary or ''} {final_output}".lower()
    if "classification" in text or "classifier" in text:
        return "classification"
    if "regression" in text or "regressor" in text:
        return "regression"
    if "report" in text:
        return "reporting"
    if "eda" in text or "explor" in text:
        return "eda"
    return "session_outcome"
