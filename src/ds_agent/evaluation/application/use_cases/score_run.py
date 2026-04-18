"""Score a single eval run against a gold task."""
# mypy: disable-error-code="no-untyped-def"


from __future__ import annotations

from collections.abc import Sequence

from ds_agent.evaluation.application.dtos.eval_report_dto import ScoredRunReport
from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.entities.human_rubric import HumanRubric
from ds_agent.evaluation.domain.ports.scorer import Scorer
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType


class ScoreRun:
    """Apply a scorer set to one run/task pair."""

    def __init__(self, scorers: Sequence[Scorer]) -> None:
        self._scorers = tuple(scorers)

    def execute(
        self,
        *,
        run: EvalRun,
        task: GoldTask,
        scorer_filters: Sequence[str] | None = None,
    ) -> ScoredRunReport:
        selected_names = set(scorer_filters or ())
        scorers = (
            [scorer for scorer in self._scorers if scorer.name in selected_names]
            if selected_names
            else list(self._scorers)
        )
        scores = {scorer.name: scorer.score(run, task) for scorer in scorers}
        scores = _apply_human_rubric_overrides(scores, run.human_rubric)
        weighted_score = 0.0
        for name, score in scores.items():
            rubric_entry = task.scoring_rubric.get(name)
            if rubric_entry is None:
                continue
            weighted_score += rubric_entry.weight * score.value
        weighted_score = max(0.0, min(1.0, weighted_score))
        decision_ready_at = run.decision_ready_at or run.finished_at
        decision_latency_seconds = (
            None
            if decision_ready_at is None
            else max(0.0, float(decision_ready_at - run.started_at))
        )
        return ScoredRunReport(
            task_id=task.id,
            run_id=run.run_id,
            mode=run.mode,
            weighted_score=weighted_score,
            passed=weighted_score >= task.pass_threshold,
            scores=scores,
            session_id=run.session_id,
            cost_usd=run.cost_usd,
            decision_latency_seconds=decision_latency_seconds,
            metric_choices=tuple(run.metric_choices),
            artifact_types=tuple(sorted(run.artifact_types())),
            run_metadata={
                "taskDomain": task.domain,
                "taskDifficulty": task.difficulty,
                "passThreshold": task.pass_threshold,
                "alertOnDropBelow": task.alert_on_drop_below,
                **dict(run.metadata),
            },
        )


def _apply_human_rubric_overrides(scores, rubric: HumanRubric | None):
    if rubric is None:
        return scores

    updated_scores = dict(scores)
    for name, value in rubric.dimensions.items():
        current = updated_scores.get(name)
        if current is None:
            continue
        rationale = f"Human rubric override by {rubric.reviewer_id}."
        if rubric.comment:
            rationale = f"{rationale} Comment: {rubric.comment}"
        updated_scores[name] = current.model_copy(
            update={
                "value": value,
                "rationale": rationale,
                "sub_scores": {
                    **current.sub_scores,
                    "auto_score": current.value,
                },
                "evidence_refs": (*current.evidence_refs, f"human_rubric:{rubric.reviewer_id}"),
                "version": f"{current.version}+human_override",
                "judge_type": JudgeType.HUMAN_OR_PROXY,
            }
        )
    return updated_scores
