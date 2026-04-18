"""Task Graph domain entities.

Represents a non-linear DAG of analysis tasks with conditional branching,
backtracking, and experiment branching. Domain layer — no external deps.
"""

from __future__ import annotations

import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum


class TaskStatus(StrEnum):
    """Task lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskNode:
    """A single task in the execution graph."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = ""
    stage: str = ""  # Maps to DS_WORKFLOW_STAGES
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    result: dict | None = None
    checkpoint_id: str | None = None
    retry_count: int = 0
    max_retries: int = 2

    @property
    def is_terminal(self) -> bool:
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED)

    @property
    def can_retry(self) -> bool:
        return self.status == TaskStatus.FAILED and self.retry_count < self.max_retries

    def start(self) -> None:
        self.status = TaskStatus.RUNNING

    def complete(self, result: dict | None = None) -> None:
        self.status = TaskStatus.COMPLETED
        self.result = result

    def fail(self, result: dict | None = None) -> None:
        self.status = TaskStatus.FAILED
        self.result = result
        self.retry_count += 1

    def skip(self) -> None:
        self.status = TaskStatus.SKIPPED

    def reset(self) -> None:
        """Reset to pending for backtracking."""
        self.status = TaskStatus.PENDING
        self.result = None


@dataclass
class ConditionalEdge:
    """A conditional edge in the task graph.

    The edge is traversed only if the condition function returns True
    when given the source node's result.
    """

    from_node_id: str
    to_node_id: str
    condition: Callable[[dict | None], bool] = field(default=lambda r: True)
    label: str = ""


class TaskGraph:
    """Directed Acyclic Graph of analysis tasks.

    Supports:
    - Linear pipeline (default DS workflow)
    - Conditional branching (based on evaluation results)
    - Backtracking (rewind to earlier stage)
    - Experiment branching (parallel experiments)
    """

    def __init__(self) -> None:
        self._nodes: dict[str, TaskNode] = {}
        self._edges: list[tuple[str, str]] = []
        self._conditional_edges: list[ConditionalEdge] = []

    @property
    def nodes(self) -> dict[str, TaskNode]:
        return dict(self._nodes)

    @property
    def edges(self) -> list[tuple[str, str]]:
        return list(self._edges)

    def add_node(self, node: TaskNode) -> None:
        """Add a task node to the graph."""
        self._nodes[node.id] = node

    def add_edge(self, from_id: str, to_id: str) -> None:
        """Add a dependency edge: to_id depends on from_id."""
        if from_id not in self._nodes or to_id not in self._nodes:
            raise ValueError(f"Both nodes must exist: {from_id}, {to_id}")
        self._edges.append((from_id, to_id))
        if from_id not in self._nodes[to_id].dependencies:
            self._nodes[to_id].dependencies.append(from_id)

    def add_conditional_edge(
        self,
        from_id: str,
        to_id: str,
        condition: Callable[[dict | None], bool],
        label: str = "",
    ) -> None:
        """Add a conditional edge — traversed only if condition(result) is True."""
        self._conditional_edges.append(
            ConditionalEdge(from_id, to_id, condition, label)
        )

    def get_node(self, node_id: str) -> TaskNode | None:
        return self._nodes.get(node_id)

    def get_ready_nodes(self) -> list[TaskNode]:
        """Return nodes whose dependencies are all completed."""
        ready = []
        for node in self._nodes.values():
            if node.status != TaskStatus.PENDING:
                continue
            deps_met = all(
                self._nodes[dep_id].status == TaskStatus.COMPLETED
                for dep_id in node.dependencies
                if dep_id in self._nodes
            )
            if deps_met:
                ready.append(node)
        return ready

    def complete_node(self, node_id: str, result: dict | None = None) -> list[str]:
        """Complete a node and evaluate conditional edges.

        Returns list of newly activated node IDs (from conditional edges).
        """
        node = self._nodes.get(node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")
        node.complete(result)

        # Evaluate conditional edges
        activated: list[str] = []
        for edge in self._conditional_edges:
            if edge.from_node_id == node_id and edge.condition(result):
                target = self._nodes.get(edge.to_node_id)
                if target and target.status == TaskStatus.SKIPPED:
                    target.reset()
                    activated.append(edge.to_node_id)

        return activated

    def rewind_to(self, node_id: str) -> list[str]:
        """Rewind: reset this node and all downstream nodes to PENDING.

        Returns list of reset node IDs.
        """
        if node_id not in self._nodes:
            raise ValueError(f"Node not found: {node_id}")

        # BFS to find all downstream nodes
        downstream = self._find_downstream(node_id)
        downstream.add(node_id)

        reset_ids: list[str] = []
        for nid in downstream:
            node = self._nodes[nid]
            if node.status != TaskStatus.PENDING:
                node.reset()
                reset_ids.append(nid)

        return reset_ids

    def branch(self, from_id: str, branch_nodes: list[TaskNode]) -> list[str]:
        """Create experiment branches from a node.

        Each branch node depends on from_id and can be run in parallel.
        Returns list of new branch node IDs.
        """
        branch_ids: list[str] = []
        for node in branch_nodes:
            self.add_node(node)
            self.add_edge(from_id, node.id)
            branch_ids.append(node.id)
        return branch_ids

    def get_best_branch(
        self,
        branch_ids: list[str],
        metric_key: str,
        higher_is_better: bool = True,
    ) -> str | None:
        """Find the branch with the best metric value."""
        best_id = None
        best_val = None
        for nid in branch_ids:
            node = self._nodes.get(nid)
            if not node or node.status != TaskStatus.COMPLETED or not node.result:
                continue
            val = node.result.get(metric_key)
            if val is None:
                continue
            if best_val is None or (
                (higher_is_better and val > best_val)
                or (not higher_is_better and val < best_val)
            ):
                best_val = val
                best_id = nid
        return best_id

    def get_completeness(self) -> dict:
        """Return graph completion statistics."""
        total = len(self._nodes)
        completed = sum(1 for n in self._nodes.values() if n.status == TaskStatus.COMPLETED)
        failed = sum(1 for n in self._nodes.values() if n.status == TaskStatus.FAILED)
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": total - completed - failed,
            "pct": round(completed / total * 100) if total else 0,
        }

    def to_dict(self) -> dict:
        """Serialize graph state for checkpointing."""
        return {
            "nodes": {
                nid: {
                    "id": n.id,
                    "name": n.name,
                    "stage": n.stage,
                    "status": n.status,
                    "dependencies": n.dependencies,
                    "result": n.result,
                    "retry_count": n.retry_count,
                }
                for nid, n in self._nodes.items()
            },
            "edges": self._edges,
        }

    def _find_downstream(self, node_id: str) -> set[str]:
        """Find all nodes downstream of the given node (BFS)."""
        # Build adjacency: from -> [to, ...]
        adj: dict[str, list[str]] = {}
        for from_id, to_id in self._edges:
            adj.setdefault(from_id, []).append(to_id)
        for ce in self._conditional_edges:
            adj.setdefault(ce.from_node_id, []).append(ce.to_node_id)

        visited: set[str] = set()
        queue: deque[str] = deque()
        for child in adj.get(node_id, []):
            queue.append(child)

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for child in adj.get(current, []):
                queue.append(child)

        return visited

    @classmethod
    def from_linear_stages(cls, stages: list[str]) -> TaskGraph:
        """Create a linear task graph from DS workflow stages."""
        graph = cls()
        prev_id: str | None = None
        for stage in stages:
            node = TaskNode(name=stage, stage=stage)
            graph.add_node(node)
            if prev_id is not None:
                graph.add_edge(prev_id, node.id)
            prev_id = node.id
        return graph
