"""Artifact faithfulness scorer."""
# mypy: disable-error-code="no-untyped-def"


from __future__ import annotations

from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.ports.judge_llm import JudgeLLM, JudgeRequest
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.evaluation.infrastructure.scorers.base import (
    build_score,
    extract_numbers,
    maybe_use_judge,
)


class ArtifactFaithfulnessScorer:
    """Check whether user-facing artifacts are numerically consistent."""

    name = "artifact_faithfulness"
    version = "0.1.0"
    judge_type = JudgeType.LLM

    def __init__(self, judge: JudgeLLM | None = None) -> None:
        self._judge = judge

    def score(self, run: EvalRun, task: GoldTask):
        relevant_artifacts = [
            artifact
            for artifact in run.artifacts
            if artifact.artifact_type not in {"ranked_customer_list", "case_queue"}
        ]
        artifact_text = " ".join(artifact.content for artifact in relevant_artifacts)
        narrative = f"{run.final_summary} {artifact_text}".strip()
        mentioned_numbers = set(extract_numbers(narrative))
        metric_numbers = {str(value) for value in run.underlying_metrics.values()}
        metric_numbers |= {f"{value:.2f}" for value in run.underlying_metrics.values()}
        for key in run.underlying_metrics:
            metric_numbers |= set(extract_numbers(key.replace("pct", "%").replace("_", " ")))
        mismatches = sorted(number for number in mentioned_numbers if number not in metric_numbers)
        artifact_presence = 1.0 if relevant_artifacts else 0.0
        narrative_lower = narrative.lower()
        supported_metrics = sum(
            1 for key in run.underlying_metrics if key.lower() in narrative_lower
        )
        support_ratio = min(1.0, supported_metrics / max(1, len(run.underlying_metrics)))
        value = (
            0.2 * artifact_presence
            + 0.4 * support_ratio
            + 0.4 * max(0.0, 1.0 - 0.25 * len(mismatches))
        )
        fallback = build_score(
            name=self.name,
            value=value,
            rationale=(
                "Artifact narrative matches tracked metrics."
                if not mismatches
                else f"Detected {len(mismatches)} unsupported numeric claim(s)."
            ),
            judge_type=self.judge_type,
            version=self.version,
            sub_scores={
                "artifact_presence": artifact_presence,
                "metric_support": support_ratio,
                "numeric_consistency": max(0.0, 1.0 - 0.25 * len(mismatches)),
            },
            evidence_refs=mismatches,
        )
        request = JudgeRequest(
            scorer_name=self.name,
            rubric_version=self.version,
            task_id=task.id,
            prompt=task.prompt,
            payload={
                "summary": run.final_summary,
                "artifacts": [artifact.model_dump(mode="json") for artifact in relevant_artifacts],
                "metrics": run.underlying_metrics,
            },
            fallback_score=fallback.value,
            fallback_rationale=fallback.rationale,
        )
        return maybe_use_judge(judge=self._judge, request=request, fallback=fallback)
