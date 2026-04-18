"""Port for persisting human rubric reviews."""

from __future__ import annotations

from typing import Protocol

from ds_agent.evaluation.domain.entities.human_rubric import HumanRubricRecord


class HumanRubricStore(Protocol):
    """Append and query persisted human rubric reviews."""

    def append(self, record: HumanRubricRecord) -> None:
        """Persist one human review record."""

    def latest(
        self,
        *,
        session_id: str,
        run_id: str | None = None,
    ) -> HumanRubricRecord | None:
        """Return the latest human review for a session or run."""
