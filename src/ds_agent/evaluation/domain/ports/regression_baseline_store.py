"""Persistence contract for frozen regression-board baselines."""

from __future__ import annotations

from typing import Protocol

from ds_agent.evaluation.domain.entities.regression_board import RegressionBoardBaseline


class RegressionBaselineStore(Protocol):
    """Read and write the latest frozen regression baseline."""

    def save(self, baseline: RegressionBoardBaseline) -> None:
        """Persist one frozen baseline."""

    def load_latest(self) -> RegressionBoardBaseline | None:
        """Load the latest frozen baseline if available."""
