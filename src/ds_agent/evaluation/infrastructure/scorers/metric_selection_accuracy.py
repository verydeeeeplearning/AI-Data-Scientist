"""Metric selection scorer."""
# mypy: disable-error-code="no-untyped-def"


from __future__ import annotations

from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.evaluation.infrastructure.scorers.base import build_score, clamp_score


class MetricSelectionAccuracyScorer:
    """Evaluate whether the chosen primary metrics fit the task."""

    name = "metric_selection_accuracy"
    version = "0.1.0"
    judge_type = JudgeType.HYBRID

    def score(self, run: EvalRun, task: GoldTask):
        validation = task.validation_points.metric_selection
        selected = {item.lower() for item in run.metric_choices}
        acceptable = (
            {item.lower() for item in validation.acceptable_primary} if validation else set()
        )
        forbidden = (
            {item.lower() for item in validation.forbidden_primary} if validation else set()
        )
        forbidden_hits = selected & forbidden
        acceptable_hits = selected & acceptable
        if forbidden_hits:
            value = 0.0
        else:
            base = 0.85 if acceptable_hits else (0.4 if selected else 0.2)
            mentions = sum(1 for item in selected if item in run.final_summary.lower())
            value = clamp_score(base + min(mentions, 2) * 0.05)
        return build_score(
            name=self.name,
            value=value,
            rationale=(
                f"Selected metrics: {sorted(selected) or ['<none>']}. "
                "Acceptable hits="
                f"{sorted(acceptable_hits)}, forbidden hits={sorted(forbidden_hits)}."
            ),
            judge_type=self.judge_type,
            version=self.version,
            sub_scores={
                "acceptable_coverage": (
                    (len(acceptable_hits) / len(acceptable)) if acceptable else 1.0
                ),
                "forbidden_penalty": 0.0 if forbidden_hits else 1.0,
            },
            evidence_refs=sorted(selected),
        )
