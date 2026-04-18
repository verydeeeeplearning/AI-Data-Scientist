"""Support ports for Decision OS promotion-gate workflows."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.promotion import PromotionDecision, RollbackPlan


@runtime_checkable
class PromotionDecisionStore(Protocol):
    """Persistence contract for promotion decisions."""

    def save(self, decision: PromotionDecision) -> None: ...

    def get(self, decision_id: str) -> PromotionDecision | None: ...

    def list_for_model(
        self,
        candidate_model_id: str,
        *,
        limit: int = 20,
    ) -> list[PromotionDecision]: ...


@runtime_checkable
class RollbackPlanLoader(Protocol):
    """Load and validate a rollback plan reference."""

    def load(self, source: str) -> RollbackPlan: ...
