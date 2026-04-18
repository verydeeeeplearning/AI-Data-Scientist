"""Session completeness scorer."""
# mypy: disable-error-code="no-untyped-def"


from __future__ import annotations

from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.evaluation.infrastructure.scorers.base import build_score, contains_placeholder


class SessionCompletenessScorer:
    """Score whether expected deliverables were actually produced."""

    name = "session_completeness"
    version = "0.1.0"
    judge_type = JudgeType.HYBRID

    def score(self, run: EvalRun, task: GoldTask):
        expected = [deliverable.type for deliverable in task.expected_deliverables]
        produced = run.artifact_types()
        matched = sum(1 for artifact_type in expected if artifact_type in produced)
        completeness = matched / len(expected) if expected else 1.0
        matched_artifacts = [
            artifact
            for artifact in run.artifacts
            if artifact.artifact_type in produced and artifact.artifact_type in expected
        ]
        placeholder_count = sum(
            1
            for artifact in matched_artifacts
            if not artifact.content.strip() or contains_placeholder(artifact.content)
        )
        quality_mult = 1.0 if placeholder_count == 0 else 0.5
        return build_score(
            name=self.name,
            value=completeness * quality_mult,
            rationale=(
                f"Produced {matched}/{len(expected)} expected deliverables with "
                f"{placeholder_count} placeholder artifact(s)."
            ),
            judge_type=self.judge_type,
            version=self.version,
            sub_scores={
                "deliverable_coverage": completeness,
                "quality_multiplier": quality_mult,
            },
            evidence_refs=sorted(produced),
        )
