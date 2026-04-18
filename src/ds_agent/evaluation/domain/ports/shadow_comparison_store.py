"""Persistence contract for shadow comparison records."""

from __future__ import annotations

from typing import Protocol

from ds_agent.evaluation.domain.entities.shadow_comparison import ShadowComparisonRecord


class ShadowComparisonStore(Protocol):
    """Append-only persistence contract for shadow comparison records."""

    def append(self, record: ShadowComparisonRecord) -> None:
        """Persist one production-vs-shadow comparison record."""

    def latest_for_baseline_run(self, baseline_run_id: str) -> ShadowComparisonRecord | None:
        """Return the newest comparison for one baseline run."""

