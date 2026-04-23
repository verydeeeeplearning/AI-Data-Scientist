"""Application use case: save a new operator-named checkpoint.

This use case orchestrates input validation and delegates persistence to a
``NamedCheckpointStorePort`` so the application layer never depends on a
concrete file-system store. Renderer-facing camelCase serialization happens
at the route boundary, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ds_agent.domain.entities.session_checkpoint import NamedCheckpoint


class NamedCheckpointStorePort(Protocol):
    """Persistence contract for operator-saved named checkpoints."""

    def save_named(
        self,
        session_id: str,
        name: str,
        *,
        transcript_step: int,
        description: str | None = None,
    ) -> NamedCheckpoint: ...


class TranscriptStepProviderPort(Protocol):
    """Resolve the current transcript step for a session.

    The use case never reads transcripts directly; it asks an injected
    provider what step to anchor the new checkpoint on. This keeps the
    save-checkpoint use case independent of any specific transcript backend.
    """

    def current_step(self, session_id: str) -> int: ...


@dataclass(frozen=True, slots=True)
class SaveNamedCheckpointInput:
    """Inputs accepted at the application boundary."""

    session_id: str
    name: str
    description: str | None = None


class SaveNamedCheckpointUseCase:
    """Save one operator-named checkpoint anchored at the current transcript."""

    def __init__(
        self,
        store: NamedCheckpointStorePort,
        step_provider: TranscriptStepProviderPort,
    ) -> None:
        self._store = store
        self._step_provider = step_provider

    def execute(self, input: SaveNamedCheckpointInput) -> NamedCheckpoint:
        session_id = input.session_id.strip()
        if not session_id:
            raise ValueError("session_id is required")
        name = input.name.strip()
        if not name:
            raise ValueError("name is required")

        description = (
            input.description.strip() if input.description and input.description.strip() else None
        )
        transcript_step = max(0, int(self._step_provider.current_step(session_id)))
        return self._store.save_named(
            session_id,
            name,
            transcript_step=transcript_step,
            description=description,
        )
