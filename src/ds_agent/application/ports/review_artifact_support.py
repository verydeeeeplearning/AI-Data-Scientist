"""Support ports for Decision OS review-artifact use cases."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.experiment import ExperimentRun
from ds_agent.domain.entities.review_artifact import ReviewArtifact


@runtime_checkable
class ExperimentReviewArtifactStore(Protocol):
    """Persist and retrieve structured review artifacts for experiment runs."""

    def get_run(self, run_id: str) -> ExperimentRun | None: ...

    def upsert_review_artifact(self, run_id: str, artifact: ReviewArtifact) -> ExperimentRun: ...
