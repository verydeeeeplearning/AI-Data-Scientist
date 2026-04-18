"""Operator satisfaction scorer."""
# mypy: disable-error-code="no-untyped-def"


from __future__ import annotations

from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.evaluation.infrastructure.scorers.base import build_score, clamp_score


class OperatorSatisfactionScorer:
    """Score satisfaction from human review or proxy signals."""

    name = "operator_satisfaction"
    version = "0.1.0"
    judge_type = JudgeType.HUMAN_OR_PROXY

    def score(self, run: EvalRun, task: GoldTask):
        feedback = run.operator_feedback
        if feedback.human_score is not None:
            human_score = feedback.human_score
            value = human_score / 5.0 if human_score > 1.0 else human_score
            rationale = "Human rubric score available."
            evidence = ["human_score"]
            sub_scores = {"proxy_signal_strength": clamp_score(value)}
        else:
            value = 1.0
            if feedback.approved_final is False:
                value -= 0.4
            if feedback.manual_intervention:
                value -= 0.3
            value -= min(feedback.follow_up_messages, 4) * 0.1
            goal_status = str(run.metadata.get("goalStatus", "") or "")
            task_status = str(run.metadata.get("taskStatus", "") or "")
            blocked_reason = str(run.metadata.get("goalBlockedReason", "") or "")
            checkpoint_present = run.metadata.get("checkpointStep") is not None

            goal_outcome_signal = 1.0
            if goal_status == "completed":
                value += 0.10
            elif goal_status == "blocked":
                goal_outcome_signal = 0.55 if blocked_reason else 0.30
                value -= 0.10 if blocked_reason else 0.25
            elif goal_status == "cancelled":
                goal_outcome_signal = 0.15
                value -= 0.35
            elif goal_status == "in_progress":
                goal_outcome_signal = 0.65
                value -= 0.10

            task_health_signal = 1.0
            if task_status == "succeeded":
                value += 0.05
            elif task_status == "failed":
                task_health_signal = 0.0
                value -= 0.25
            elif task_status == "cancelled":
                task_health_signal = 0.25
                value -= 0.15

            recovery_continuity = (
                1.0
                if checkpoint_present
                and task_status == "succeeded"
                and (
                    goal_status == "completed"
                    or (goal_status == "blocked" and bool(blocked_reason))
                )
                else 0.0
            )
            if recovery_continuity > 0:
                value += 0.05

            rationale = "Proxy score derived from operator follow-up and runtime recovery signals."
            evidence = [
                f"approved_final={feedback.approved_final}",
                f"manual_intervention={feedback.manual_intervention}",
                f"follow_up_messages={feedback.follow_up_messages}",
                f"goal_status={goal_status or 'unknown'}",
                f"task_status={task_status or 'unknown'}",
                f"checkpoint_present={checkpoint_present}",
                f"blocked_reason_present={bool(blocked_reason)}",
            ]
            sub_scores = {
                "proxy_signal_strength": clamp_score(value),
                "goal_outcome_signal": clamp_score(goal_outcome_signal),
                "task_health_signal": clamp_score(task_health_signal),
                "recovery_continuity": clamp_score(recovery_continuity),
            }
        return build_score(
            name=self.name,
            value=clamp_score(value),
            rationale=rationale,
            judge_type=self.judge_type,
            version=self.version,
            sub_scores=sub_scores,
            evidence_refs=evidence,
        )
