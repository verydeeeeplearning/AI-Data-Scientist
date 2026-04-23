"""Application use case: branch an agent run from a parent run.

The use case orchestrates parent-run lookup, optional named-checkpoint
resolution, and delegates the actual run start to an injected port. The
returned ``BranchedRun`` carries enough metadata to render lineage in the
renderer without an extra round-trip.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ds_agent.domain.entities.runtime_state import RunState
from ds_agent.domain.entities.session_checkpoint import NamedCheckpoint


class ParentRunLookupPort(Protocol):
    """Resolve a parent ``RunState`` by id without exposing storage details."""

    def get(self, run_id: str) -> RunState | None: ...


class NamedCheckpointLookupPort(Protocol):
    """Resolve a previously-saved named checkpoint by id."""

    def get_named(self, checkpoint_id: str) -> NamedCheckpoint | None: ...


class StartBranchedRunPort(Protocol):
    """Spawn a tracked agent run inheriting branch lineage from a parent."""

    async def start_branched_run(
        self,
        *,
        session_id: str,
        message: str,
        parent_run_id: str,
        resume_from_checkpoint: bool,
        model: str | None,
    ) -> RunState: ...


@dataclass(frozen=True, slots=True)
class BranchRunInput:
    """Inputs accepted at the application boundary."""

    parent_run_id: str
    message: str
    checkpoint_id: str | None = None
    model: str | None = None


@dataclass(frozen=True, slots=True)
class BranchedRun:
    """Output of a branch operation."""

    run: RunState
    parent_run_id: str
    checkpoint: NamedCheckpoint | None


class BranchRunUseCase:
    """Spawn a branched agent run from a parent run + optional checkpoint."""

    def __init__(
        self,
        parent_lookup: ParentRunLookupPort,
        checkpoint_lookup: NamedCheckpointLookupPort,
        starter: StartBranchedRunPort,
    ) -> None:
        self._parents = parent_lookup
        self._checkpoints = checkpoint_lookup
        self._starter = starter

    async def execute(self, input: BranchRunInput) -> BranchedRun:
        parent_run_id = input.parent_run_id.strip()
        if not parent_run_id:
            raise ValueError("parent_run_id is required")
        message = input.message.strip()
        if not message:
            raise ValueError("message is required")

        parent = self._parents.get(parent_run_id)
        if parent is None:
            raise ValueError(f"Unknown parent run: {parent_run_id}")

        checkpoint: NamedCheckpoint | None = None
        if input.checkpoint_id is not None and input.checkpoint_id.strip():
            checkpoint = self._checkpoints.get_named(input.checkpoint_id.strip())
            if checkpoint is None:
                raise ValueError(f"Unknown checkpoint: {input.checkpoint_id.strip()}")
            if checkpoint.session_id != parent.session_id:
                raise ValueError(
                    "checkpoint does not belong to the parent run's session"
                )

        run = await self._starter.start_branched_run(
            session_id=parent.session_id,
            message=message,
            parent_run_id=parent.run_id,
            resume_from_checkpoint=checkpoint is not None,
            model=input.model,
        )
        return BranchedRun(run=run, parent_run_id=parent.run_id, checkpoint=checkpoint)
