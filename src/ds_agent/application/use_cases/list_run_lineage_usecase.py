"""Application use case: list the branch / rerun lineage for one run family.

The renderer only needs a simple tree-friendly view of runtime runs. This use
case accepts any run id in the family, walks upward to the true root using
``branched_from_run_id``, then returns the connected subtree as a depth-ordered
preorder traversal that the UI can render as an indented list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ds_agent.domain.entities.runtime_state import RunState

_LINEAGE_LIST_LIMIT = 5000


class RunLineageLookupPort(Protocol):
    """Resolve one run and list candidate sibling runs from the same store."""

    def get(self, run_id: str) -> RunState | None: ...

    def list(
        self,
        *,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[RunState]: ...


@dataclass(frozen=True, slots=True)
class RunLineageNode:
    """One renderer-facing lineage row."""

    run: RunState
    depth: int
    is_root: bool
    is_seed: bool


@dataclass(frozen=True, slots=True)
class ListRunLineageResult:
    """Immutable lineage payload returned to the interface layer."""

    root_run_id: str
    seed_run_id: str
    nodes: tuple[RunLineageNode, ...]


class ListRunLineageUseCase:
    """List the connected lineage tree for one runtime run family."""

    def __init__(self, runs: RunLineageLookupPort) -> None:
        self._runs = runs

    def execute(self, root_run_id: str) -> ListRunLineageResult:
        requested_run_id = root_run_id.strip()
        if not requested_run_id:
            raise ValueError("root_run_id is required")

        seed = self._runs.get(requested_run_id)
        if seed is None:
            raise ValueError(f"Unknown run: {requested_run_id}")

        candidates = self._runs.list(
            session_id=seed.session_id,
            limit=_LINEAGE_LIST_LIMIT,
        )
        by_id: dict[str, RunState] = {run.run_id: run for run in candidates}
        by_id[seed.run_id] = seed

        root = seed
        seen_parent_ids = {seed.run_id}
        while root.branched_from_run_id:
            parent_id = root.branched_from_run_id.strip()
            if not parent_id or parent_id in seen_parent_ids:
                break
            parent = by_id.get(parent_id) or self._runs.get(parent_id)
            if parent is None or parent.session_id != seed.session_id:
                break
            by_id[parent.run_id] = parent
            seen_parent_ids.add(parent.run_id)
            root = parent

        children_by_parent: dict[str, list[RunState]] = {}
        for run in by_id.values():
            parent_id = (run.branched_from_run_id or "").strip()
            if not parent_id:
                continue
            parent = by_id.get(parent_id)
            if parent is None or parent.session_id != seed.session_id:
                continue
            children_by_parent.setdefault(parent_id, []).append(run)

        for children in children_by_parent.values():
            children.sort(key=lambda item: (item.created_at, item.run_id))

        ordered_nodes: list[RunLineageNode] = []

        def walk(run: RunState, depth: int) -> None:
            ordered_nodes.append(
                RunLineageNode(
                    run=run,
                    depth=depth,
                    is_root=depth == 0,
                    is_seed=run.run_id == seed.run_id,
                )
            )
            for child in children_by_parent.get(run.run_id, []):
                walk(child, depth + 1)

        walk(root, 0)
        return ListRunLineageResult(
            root_run_id=root.run_id,
            seed_run_id=seed.run_id,
            nodes=tuple(ordered_nodes),
        )
