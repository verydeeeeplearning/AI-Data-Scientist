"""Heuristic scoping accuracy scorer."""
# mypy: disable-error-code="no-untyped-def"


from __future__ import annotations

from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.ports.judge_llm import JudgeLLM, JudgeRequest
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.evaluation.infrastructure.scorers.base import build_score, maybe_use_judge


class ScopingAccuracyScorer:
    """Score how well the goal brief translates the business problem."""

    name = "scoping_accuracy"
    version = "0.1.0"
    judge_type = JudgeType.LLM

    def __init__(self, judge: JudgeLLM | None = None) -> None:
        self._judge = judge

    def score(self, run: EvalRun, task: GoldTask):
        goal_fields = {key for key, value in run.goal_brief.items() if str(value).strip()}
        goal_deliverable = next(
            (item for item in task.expected_deliverables if item.type == "goal_brief"),
            None,
        )
        required_sections = set(goal_deliverable.must_contain if goal_deliverable else ())
        required_coverage = (
            (len(required_sections & goal_fields) / len(required_sections))
            if required_sections
            else 1.0
        )
        core_fields = {"business_question", "ds_problem_statement", "decision_to_make"}
        core_coverage = len(core_fields & goal_fields) / len(core_fields)
        fallback = build_score(
            name=self.name,
            value=0.6 * required_coverage + 0.4 * core_coverage,
            rationale=(
                "Goal brief covers "
                f"{len(required_sections & goal_fields)}/{len(required_sections) or 0} "
                "required sections and "
                f"{len(core_fields & goal_fields)}/{len(core_fields)} core fields."
            ),
            judge_type=self.judge_type,
            version=self.version,
            sub_scores={
                "required_sections": required_coverage,
                "core_fields": core_coverage,
            },
            evidence_refs=goal_fields,
        )
        request = JudgeRequest(
            scorer_name=self.name,
            rubric_version=self.version,
            task_id=task.id,
            prompt=task.prompt,
            payload={
                "goal_brief": run.goal_brief,
                "required_sections": sorted(required_sections),
            },
            fallback_score=fallback.value,
            fallback_rationale=fallback.rationale,
        )
        return maybe_use_judge(judge=self._judge, request=request, fallback=fallback)
