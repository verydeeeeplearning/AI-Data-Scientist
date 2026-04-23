"""Application use case: promote one result card to an audience-tagged artifact.

The use case validates inputs at the application boundary and delegates
persistence to a ``PromotedArtifactStorePort``. The returned record is the
frozen ``PromotedArtifact`` domain entity so callers can rely on equality and
immutability when relaying lineage back to the renderer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ds_agent.domain.entities.run_lineage import (
    PROMOTED_ARTIFACT_AUDIENCES,
    PromotedArtifact,
)


class PromotedArtifactStorePort(Protocol):
    """Persistence contract for operator-promoted artifacts."""

    def save_promoted_artifact(
        self,
        *,
        run_id: str,
        card_id: str,
        audience: str,
        title: str,
    ) -> PromotedArtifact: ...


@dataclass(frozen=True, slots=True)
class PromoteToArtifactInput:
    """Inputs accepted at the application boundary."""

    run_id: str
    card_id: str
    audience: str
    title: str | None = None


class PromoteToArtifactUseCase:
    """Promote one result card into a persisted, audience-tagged artifact."""

    def __init__(self, store: PromotedArtifactStorePort) -> None:
        self._store = store

    def execute(self, input: PromoteToArtifactInput) -> PromotedArtifact:
        run_id = input.run_id.strip()
        if not run_id:
            raise ValueError("run_id is required")
        card_id = input.card_id.strip()
        if not card_id:
            raise ValueError("card_id is required")
        audience = input.audience.strip().lower()
        if audience not in PROMOTED_ARTIFACT_AUDIENCES:
            raise ValueError(
                "audience must be one of: " + ", ".join(PROMOTED_ARTIFACT_AUDIENCES)
            )
        title = (
            input.title.strip()
            if input.title is not None and input.title.strip()
            else card_id
        )
        return self._store.save_promoted_artifact(
            run_id=run_id,
            card_id=card_id,
            audience=audience,
            title=title,
        )
