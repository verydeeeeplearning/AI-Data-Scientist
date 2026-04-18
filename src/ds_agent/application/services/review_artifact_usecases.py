"""Decision OS review-artifact use cases."""

from __future__ import annotations

from datetime import datetime

from ds_agent.application.ports.review_artifact_support import ExperimentReviewArtifactStore
from ds_agent.domain.entities.experiment import ExperimentRun
from ds_agent.domain.entities.review_artifact import (
    ReviewArtifact,
    ReviewSkillName,
    build_review_artifact,
)


class RecordReviewArtifactUseCase:
    """Validate and persist one structured review artifact for a run."""

    def __init__(self, runs: ExperimentReviewArtifactStore) -> None:
        self._runs = runs

    def execute(
        self,
        *,
        run_id: str,
        skill_name: ReviewSkillName,
        summary: str,
        artifact: dict[str, object],
        narrative: str | None = None,
        artifact_id: str | None = None,
        created_at: datetime | None = None,
    ) -> ExperimentRun:
        review_artifact = build_review_artifact(
            skill_name=skill_name,
            summary=summary,
            artifact=artifact,
            narrative=narrative,
            artifact_id=artifact_id,
            created_at=created_at,
        )
        return self._runs.upsert_review_artifact(run_id, review_artifact)


class GetReviewArtifactsUseCase:
    """Return the structured review artifacts stored for one run."""

    def __init__(self, runs: ExperimentReviewArtifactStore) -> None:
        self._runs = runs

    def execute(self, run_id: str) -> list[ReviewArtifact]:
        run = self._runs.get_run(run_id)
        if run is None:
            raise LookupError(f"Experiment run not found: {run_id}")
        return run.review_artifacts
