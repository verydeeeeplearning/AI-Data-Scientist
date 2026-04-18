"""Tool trajectory scorer."""
# mypy: disable-error-code="no-untyped-def"


from __future__ import annotations

from itertools import pairwise

from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.evaluation.infrastructure.scorers.base import build_score, clamp_score

_ORDERED_STAGE_TOOLS = (
    "load_data",
    "profile_data",
    "run_eda",
    "build_features",
    "train_model",
    "evaluate_model",
    "generate_report",
)


class ToolTrajectoryScorer:
    """Score tool efficiency and ordering."""

    name = "tool_trajectory"
    version = "0.1.0"
    judge_type = JudgeType.DETERMINISTIC

    def score(self, run: EvalRun, task: GoldTask):
        tool_calls = list(run.tool_calls)
        total = len(tool_calls) or 1
        redundant = 0
        for previous, current in pairwise(tool_calls):
            if previous.name == current.name and previous.arguments == current.arguments:
                redundant += 1
        failed = sum(1 for call in tool_calls if call.status == "error")
        name_to_index = {name: idx for idx, name in enumerate(_ORDERED_STAGE_TOOLS)}
        highest_seen = -1
        order_violations = 0
        for call in tool_calls:
            order_index = name_to_index.get(call.name)
            if order_index is None:
                continue
            if order_index < highest_seen:
                order_violations += 1
            highest_seen = max(highest_seen, order_index)
        total_cost = sum(call.cost_usd for call in tool_calls)
        budget = task.input.budget_usd
        budget_overshoot = 0.0 if budget <= 0 else max(0.0, total_cost - budget) / budget
        penalty = (
            0.35 * (redundant / total)
            + 0.35 * (failed / total)
            + 0.2 * clamp_score(order_violations / total)
            + 0.1 * clamp_score(budget_overshoot)
        )
        return build_score(
            name=self.name,
            value=1.0 - penalty,
            rationale=(
                f"{len(tool_calls)} tool calls, {redundant} redundant, {failed} failed, "
                f"{order_violations} order violations."
            ),
            judge_type=self.judge_type,
            version=self.version,
            sub_scores={
                "redundant_ratio": clamp_score(1.0 - redundant / total),
                "failed_ratio": clamp_score(1.0 - failed / total),
                "budget_adherence": clamp_score(1.0 - budget_overshoot),
            },
            evidence_refs=[call.name for call in tool_calls],
        )
