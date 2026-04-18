"""Time-to-decision scorer."""
# mypy: disable-error-code="no-untyped-def"


from __future__ import annotations

from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.evaluation.infrastructure.scorers.base import build_score, clamp_score


class TimeToDecisionScorer:
    """Score how quickly the run becomes decision-ready."""

    name = "time_to_decision"
    version = "0.1.0"
    judge_type = JudgeType.DETERMINISTIC

    def score(self, run: EvalRun, task: GoldTask):
        decision_ready_at = run.decision_ready_at or run.finished_at or run.started_at
        elapsed_min = max(0.0, (decision_ready_at - run.started_at) / 60.0)
        target = float(task.input.time_budget_min or 0)
        value = (
            1.0
            if target <= 0
            else clamp_score(1.0 - max(0.0, elapsed_min - target) / target)
        )
        return build_score(
            name=self.name,
            value=value,
            rationale=(
                f"Decision readiness took {elapsed_min:.1f} min against target "
                f"{target:.1f} min."
            ),
            judge_type=self.judge_type,
            version=self.version,
            sub_scores={"within_budget": value},
            evidence_refs=[f"elapsed_min={elapsed_min:.1f}", f"target_min={target:.1f}"],
        )
