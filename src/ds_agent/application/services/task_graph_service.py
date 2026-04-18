"""TaskGraphService — application layer orchestration for task graphs.

Manages the lifecycle of a TaskGraph: creation from workflow stages,
advancement, completion, backtracking, and checkpoint/restore.
"""

from __future__ import annotations

import json
from pathlib import Path

from ds_agent.domain.entities.task_graph import TaskGraph, TaskNode, TaskStatus


class TaskGraphService:
    """Orchestrates task graph execution.

    Provides higher-level operations on top of the TaskGraph entity,
    including persistence and integration with the workflow tracker.
    """

    def __init__(self, storage_dir: str | None = None) -> None:
        self._graph: TaskGraph | None = None
        self._storage_dir = Path(storage_dir) if storage_dir else None
        if self._storage_dir:
            self._storage_dir.mkdir(parents=True, exist_ok=True)

    @property
    def graph(self) -> TaskGraph | None:
        return self._graph

    def create_from_workflow(self, stages: list[str] | None = None) -> TaskGraph:
        """Create a linear task graph from DS workflow stages."""
        if stages is None:
            stages = [
                "scoping", "data_loading", "profiling", "eda",
                "feature_eng", "modeling", "evaluation", "reporting",
            ]
        self._graph = TaskGraph.from_linear_stages(stages)
        return self._graph

    def advance(self) -> list[TaskNode]:
        """Get the next executable nodes (all dependencies completed)."""
        if not self._graph:
            return []
        return self._graph.get_ready_nodes()

    def start_node(self, node_id: str) -> TaskNode | None:
        """Mark a node as running."""
        if not self._graph:
            return None
        node = self._graph.get_node(node_id)
        if node and node.status == TaskStatus.PENDING:
            node.start()
            return node
        return None

    def complete_node(
        self, node_id: str, result: dict | None = None
    ) -> list[str]:
        """Complete a node and return newly activated conditional nodes."""
        if not self._graph:
            return []
        return self._graph.complete_node(node_id, result)

    def fail_node(self, node_id: str, result: dict | None = None) -> bool:
        """Mark a node as failed. Returns True if it can be retried."""
        if not self._graph:
            return False
        node = self._graph.get_node(node_id)
        if not node:
            return False
        node.fail(result)
        return node.can_retry

    def rewind_to(self, node_id: str) -> list[str]:
        """Rewind graph to a specific node, resetting downstream."""
        if not self._graph:
            return []
        return self._graph.rewind_to(node_id)

    def get_completeness(self) -> dict:
        """Return graph completion statistics."""
        if not self._graph:
            return {"total": 0, "completed": 0, "pct": 0}
        return self._graph.get_completeness()

    def checkpoint(self, session_id: str) -> str:
        """Save current graph state. Returns checkpoint ID."""
        if not self._graph:
            raise ValueError("No graph to checkpoint")
        state = self._graph.to_dict()
        checkpoint_id = f"cp-{session_id}"

        if self._storage_dir:
            path = self._storage_dir / f"{checkpoint_id}.json"
            path.write_text(json.dumps(state, indent=2))

        return checkpoint_id

    def restore(self, checkpoint_id: str) -> TaskGraph | None:
        """Restore graph from a checkpoint."""
        if not self._storage_dir:
            return None
        path = self._storage_dir / f"{checkpoint_id}.json"
        if not path.exists():
            return None

        data = json.loads(path.read_text())
        graph = TaskGraph()
        for _nid, ndata in data.get("nodes", {}).items():
            node = TaskNode(
                id=ndata["id"],
                name=ndata["name"],
                stage=ndata.get("stage", ""),
                dependencies=ndata.get("dependencies", []),
                result=ndata.get("result"),
                retry_count=ndata.get("retry_count", 0),
            )
            node.status = TaskStatus(ndata["status"])
            graph.add_node(node)

        for from_id, to_id in data.get("edges", []):
            if from_id in graph.nodes and to_id in graph.nodes:
                graph._edges.append((from_id, to_id))

        self._graph = graph
        return graph
