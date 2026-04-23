"""Application use case: rerun an agent run anchored at a specific plan node.

The use case reuses the existing branched-run launch mechanics: the new run
inherits the parent's session and is recorded as ``branched_from_run_id`` so
downstream lineage (UI tree, scorecards) continues to work. The
``rerun_from_node_id`` is recorded on the resulting ``RunState`` so consumers
can tell apart a manual branch ("explore alternative model") from an
operator-driven rerun-from-step ("redo feature engineering only").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ds_agent.domain.entities.runtime_state import RunState


class ParentRunLookupPort(Protocol):
    """Resolve a parent ``RunState`` by id without exposing storage details."""

    def get(self, run_id: str) -> RunState | None: ...


class StartRerunFromStepPort(Protocol):
    """Spawn a tracked agent run inheriting branch lineage + node anchor."""

    async def start_rerun_from_step(
        self,
        *,
        session_id: str,
        message: str,
        parent_run_id: str,
        plan_node_id: str,
        model: str | None,
    ) -> RunState: ...


@dataclass(frozen=True, slots=True)
class RerunFromStepInput:
    """Inputs accepted at the application boundary."""

    parent_run_id: str
    plan_node_id: str
    message_override: str | None = None
    model: str | None = None


@dataclass(frozen=True, slots=True)
class RerunFromStepResult:
    """Output of a rerun-from-step operation."""

    run: RunState
    parent_run_id: str
    plan_node_id: str


class RerunFromStepUseCase:
    """Spawn a rerun anchored at one plan-tree node of a parent run."""

    def __init__(
        self,
        parent_lookup: ParentRunLookupPort,
        starter: StartRerunFromStepPort,
    ) -> None:
        self._parents = parent_lookup
        self._starter = starter

    async def execute(self, input: RerunFromStepInput) -> RerunFromStepResult:
        parent_run_id = input.parent_run_id.strip()
        if not parent_run_id:
            raise ValueError("parent_run_id is required")
        plan_node_id = input.plan_node_id.strip()
        if not plan_node_id:
            raise ValueError("plan_node_id is required")

        parent = self._parents.get(parent_run_id)
        if parent is None:
            raise ValueError(f"Unknown parent run: {parent_run_id}")

        # The override is optional. When the operator does not supply a new
        # prompt we fall back to the parent's last recorded message so the
        # rerun is reproducible without forcing the operator to retype it.
        if input.message_override is not None and input.message_override.strip():
            message = input.message_override.strip()
        else:
            message = parent.message.strip()
        if not message:
            raise ValueError("rerun message is required")

        run = await self._starter.start_rerun_from_step(
            session_id=parent.session_id,
            message=message,
            parent_run_id=parent.run_id,
            plan_node_id=plan_node_id,
            model=input.model,
        )
        return RerunFromStepResult(
            run=run,
            parent_run_id=parent.run_id,
            plan_node_id=plan_node_id,
        )
