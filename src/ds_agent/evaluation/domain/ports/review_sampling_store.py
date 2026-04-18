"""Persistence contract for review-sampling decisions."""

from __future__ import annotations

from typing import Protocol

from ds_agent.evaluation.domain.entities.review_sampling import ReviewSamplingDecision


class ReviewSamplingStore(Protocol):
    """Append-only storage for review-sampling decisions."""

    def append(self, record: ReviewSamplingDecision) -> None:
        """Persist one sampling decision."""

    def latest(
        self,
        *,
        session_id: str,
        run_id: str | None = None,
    ) -> ReviewSamplingDecision | None:
        """Return the newest matching sampling decision."""

