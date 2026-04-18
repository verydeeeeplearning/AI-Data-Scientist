"""Eval dataset persistence port."""

from __future__ import annotations

from typing import Protocol

from ds_agent.evaluation.domain.entities.eval_score import EvalDatasetRecord


class EvalDatasetStore(Protocol):
    """Append-only persistence contract for eval records."""

    def append(self, record: EvalDatasetRecord) -> None:
        """Persist one dataset record."""

    def load_all(self) -> list[EvalDatasetRecord]:
        """Load every dataset record."""
