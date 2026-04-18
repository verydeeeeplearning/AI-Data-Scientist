"""TaskGraphService tests."""

import pytest

from ds_agent.application.services.task_graph_service import TaskGraphService
from ds_agent.domain.entities.task_graph import TaskStatus


class TestTaskGraphServiceCreation:
    def test_create_default_workflow(self):
        svc = TaskGraphService()
        graph = svc.create_from_workflow()
        assert len(graph.nodes) == 8

    def test_create_custom_stages(self):
        svc = TaskGraphService()
        graph = svc.create_from_workflow(["a", "b", "c"])
        assert len(graph.nodes) == 3


class TestTaskGraphServiceAdvance:
    def test_advance_returns_first_node(self):
        svc = TaskGraphService()
        svc.create_from_workflow(["a", "b", "c"])
        ready = svc.advance()
        assert len(ready) == 1
        assert ready[0].stage == "a"

    def test_advance_after_completion(self):
        svc = TaskGraphService()
        svc.create_from_workflow(["a", "b", "c"])
        ready = svc.advance()
        node_a = ready[0]

        svc.start_node(node_a.id)
        svc.complete_node(node_a.id, {"done": True})

        ready = svc.advance()
        assert len(ready) == 1
        assert ready[0].stage == "b"


class TestTaskGraphServiceFail:
    def test_fail_node_can_retry(self):
        svc = TaskGraphService()
        svc.create_from_workflow(["a"])
        ready = svc.advance()
        node = ready[0]
        svc.start_node(node.id)

        can_retry = svc.fail_node(node.id, {"error": "OOM"})
        assert can_retry is True

    def test_fail_node_exhausted(self):
        svc = TaskGraphService()
        svc.create_from_workflow(["a"])
        ready = svc.advance()
        node = ready[0]

        svc.start_node(node.id)
        svc.fail_node(node.id)
        svc.fail_node(node.id)
        can_retry = svc.fail_node(node.id)
        # max_retries=2, so 3rd fail means can't retry
        assert can_retry is False


class TestTaskGraphServiceRewind:
    def test_rewind_to_earlier_stage(self):
        svc = TaskGraphService()
        svc.create_from_workflow(["a", "b", "c"])
        nodes = list(svc.graph.nodes.values())

        for n in nodes:
            svc.start_node(n.id)
            svc.complete_node(n.id)

        # Rewind to "b"
        reset_ids = svc.rewind_to(nodes[1].id)
        assert len(reset_ids) >= 2  # b and c reset

        comp = svc.get_completeness()
        assert comp["completed"] == 1  # only "a"


class TestTaskGraphServiceCheckpoint:
    def test_checkpoint_and_restore(self, tmp_path):
        svc = TaskGraphService(storage_dir=str(tmp_path))
        svc.create_from_workflow(["a", "b", "c"])
        nodes = list(svc.graph.nodes.values())

        svc.start_node(nodes[0].id)
        svc.complete_node(nodes[0].id, {"result": "ok"})

        # Checkpoint
        cp_id = svc.checkpoint("test-session")

        # New service, restore
        svc2 = TaskGraphService(storage_dir=str(tmp_path))
        restored = svc2.restore(cp_id)

        assert restored is not None
        assert len(restored.nodes) == 3

        # First node should be completed
        restored_nodes = list(restored.nodes.values())
        completed_nodes = [n for n in restored_nodes if n.status == TaskStatus.COMPLETED]
        assert len(completed_nodes) == 1

    def test_restore_nonexistent(self, tmp_path):
        svc = TaskGraphService(storage_dir=str(tmp_path))
        result = svc.restore("nonexistent")
        assert result is None
