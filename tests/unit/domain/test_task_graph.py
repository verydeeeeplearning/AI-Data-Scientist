"""TaskNode and TaskGraph domain entity tests."""

import pytest

from ds_agent.domain.entities.task_graph import TaskGraph, TaskNode, TaskStatus


class TestTaskNode:
    def test_default_state(self):
        node = TaskNode(name="eda", stage="eda")
        assert node.status == TaskStatus.PENDING
        assert node.is_terminal is False

    def test_lifecycle(self):
        node = TaskNode(name="modeling")
        node.start()
        assert node.status == TaskStatus.RUNNING

        node.complete({"accuracy": 0.85})
        assert node.status == TaskStatus.COMPLETED
        assert node.is_terminal is True
        assert node.result["accuracy"] == 0.85

    def test_fail_and_retry(self):
        node = TaskNode(name="modeling", max_retries=2)
        node.start()
        node.fail({"error": "OOM"})
        assert node.status == TaskStatus.FAILED
        assert node.retry_count == 1
        assert node.can_retry is True

        node.fail()
        assert node.retry_count == 2
        assert node.can_retry is False

    def test_skip(self):
        node = TaskNode(name="deployment")
        node.skip()
        assert node.status == TaskStatus.SKIPPED
        assert node.is_terminal is True

    def test_reset(self):
        node = TaskNode(name="eda")
        node.start()
        node.complete({"charts": 5})
        node.reset()
        assert node.status == TaskStatus.PENDING
        assert node.result is None


class TestTaskGraphBasic:
    def test_add_node_and_edge(self):
        g = TaskGraph()
        n1 = TaskNode(name="a", stage="a")
        n2 = TaskNode(name="b", stage="b")
        g.add_node(n1)
        g.add_node(n2)
        g.add_edge(n1.id, n2.id)

        assert len(g.nodes) == 2
        assert len(g.edges) == 1
        assert n1.id in g.nodes[n2.id].dependencies

    def test_add_edge_invalid_node(self):
        g = TaskGraph()
        n1 = TaskNode(name="a")
        g.add_node(n1)
        with pytest.raises(ValueError):
            g.add_edge(n1.id, "nonexistent")

    def test_get_ready_nodes(self):
        g = TaskGraph()
        n1 = TaskNode(name="a")
        n2 = TaskNode(name="b")
        n3 = TaskNode(name="c")
        g.add_node(n1)
        g.add_node(n2)
        g.add_node(n3)
        g.add_edge(n1.id, n2.id)
        g.add_edge(n2.id, n3.id)

        # Only n1 is ready (no dependencies)
        ready = g.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].id == n1.id

    def test_ready_nodes_after_completion(self):
        g = TaskGraph()
        n1 = TaskNode(name="a")
        n2 = TaskNode(name="b")
        g.add_node(n1)
        g.add_node(n2)
        g.add_edge(n1.id, n2.id)

        # Complete n1
        g.complete_node(n1.id, {"done": True})

        # Now n2 is ready
        ready = g.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].id == n2.id

    def test_parallel_ready_nodes(self):
        """Two nodes with same dependency become ready simultaneously."""
        g = TaskGraph()
        root = TaskNode(name="root")
        branch_a = TaskNode(name="branch_a")
        branch_b = TaskNode(name="branch_b")
        g.add_node(root)
        g.add_node(branch_a)
        g.add_node(branch_b)
        g.add_edge(root.id, branch_a.id)
        g.add_edge(root.id, branch_b.id)

        g.complete_node(root.id)
        ready = g.get_ready_nodes()
        assert len(ready) == 2


class TestTaskGraphConditionalEdge:
    def test_conditional_edge(self):
        g = TaskGraph()
        eval_node = TaskNode(name="evaluation")
        fe_node = TaskNode(name="feature_eng")
        report_node = TaskNode(name="reporting")
        g.add_node(eval_node)
        g.add_node(fe_node)
        g.add_node(report_node)

        fe_node.skip()  # Initially skipped (not on main path)

        # If accuracy < 0.7, activate feature_eng
        g.add_conditional_edge(
            eval_node.id, fe_node.id,
            condition=lambda r: r is not None and r.get("accuracy", 1.0) < 0.7,
            label="poor_performance",
        )

        # Complete evaluation with poor accuracy
        activated = g.complete_node(eval_node.id, {"accuracy": 0.55})
        assert fe_node.id in activated
        assert fe_node.status == TaskStatus.PENDING

    def test_conditional_edge_not_triggered(self):
        g = TaskGraph()
        eval_node = TaskNode(name="evaluation")
        fe_node = TaskNode(name="feature_eng")
        g.add_node(eval_node)
        g.add_node(fe_node)
        fe_node.skip()

        g.add_conditional_edge(
            eval_node.id, fe_node.id,
            condition=lambda r: r is not None and r.get("accuracy", 1.0) < 0.7,
        )

        activated = g.complete_node(eval_node.id, {"accuracy": 0.92})
        assert len(activated) == 0
        assert fe_node.status == TaskStatus.SKIPPED


class TestTaskGraphRewind:
    def test_rewind_resets_downstream(self):
        g = TaskGraph.from_linear_stages(["a", "b", "c", "d"])
        nodes = list(g.nodes.values())

        # Complete all
        for n in nodes:
            g.complete_node(n.id)

        # Rewind to 'b' (index 1)
        b_id = nodes[1].id
        reset = g.rewind_to(b_id)

        assert g.nodes[nodes[0].id].status == TaskStatus.COMPLETED  # a preserved
        assert g.nodes[nodes[1].id].status == TaskStatus.PENDING  # b reset
        assert g.nodes[nodes[2].id].status == TaskStatus.PENDING  # c reset
        assert g.nodes[nodes[3].id].status == TaskStatus.PENDING  # d reset

    def test_rewind_invalid_node(self):
        g = TaskGraph()
        with pytest.raises(ValueError):
            g.rewind_to("nonexistent")


class TestTaskGraphBranching:
    def test_experiment_branching(self):
        g = TaskGraph()
        root = TaskNode(name="modeling")
        g.add_node(root)

        exp_a = TaskNode(name="exp_xgboost", stage="modeling")
        exp_b = TaskNode(name="exp_lightgbm", stage="modeling")

        branch_ids = g.branch(root.id, [exp_a, exp_b])
        assert len(branch_ids) == 2

        g.complete_node(root.id)
        ready = g.get_ready_nodes()
        assert len(ready) == 2

    def test_get_best_branch(self):
        g = TaskGraph()
        root = TaskNode(name="root")
        g.add_node(root)

        exp_a = TaskNode(name="exp_a")
        exp_b = TaskNode(name="exp_b")
        branch_ids = g.branch(root.id, [exp_a, exp_b])

        g.complete_node(root.id)
        g.complete_node(exp_a.id, {"accuracy": 0.85})
        g.complete_node(exp_b.id, {"accuracy": 0.92})

        best = g.get_best_branch(branch_ids, "accuracy", higher_is_better=True)
        assert best == exp_b.id


class TestTaskGraphLinear:
    def test_from_linear_stages(self):
        stages = ["scoping", "data_loading", "profiling", "eda"]
        g = TaskGraph.from_linear_stages(stages)

        assert len(g.nodes) == 4
        assert len(g.edges) == 3

        # Only first node should be ready
        ready = g.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].stage == "scoping"


class TestTaskGraphCompleteness:
    def test_completeness(self):
        g = TaskGraph.from_linear_stages(["a", "b", "c"])
        nodes = list(g.nodes.values())
        g.complete_node(nodes[0].id)

        comp = g.get_completeness()
        assert comp["total"] == 3
        assert comp["completed"] == 1
        assert comp["pct"] == 33


class TestTaskGraphSerialization:
    def test_to_dict(self):
        g = TaskGraph.from_linear_stages(["a", "b"])
        d = g.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert len(d["nodes"]) == 2
