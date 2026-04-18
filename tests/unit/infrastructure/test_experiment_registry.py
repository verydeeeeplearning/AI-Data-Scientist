"""Tests for experiment registry extensions and comparison utilities."""

from __future__ import annotations

from ds_agent.memory.experiment_compare import ExperimentComparer
from ds_agent.memory.experiment_log import ExperimentLog


def _log(tmp_path) -> ExperimentLog:
    return ExperimentLog(data_dir=str(tmp_path / "exp"))


class TestExperimentRegistry:
    def test_logs_dataset_and_feature_hashes(self, tmp_path):
        log = _log(tmp_path)
        exp_id = log.log_experiment(
            project_id="proj-1",
            model_type="lightgbm",
            task_type="classification",
            metrics={"f1": 0.81},
            dataset_hash="dataset-hash",
            feature_recipe_hash="feature-hash",
            decision_memo="Selected LightGBM for stronger lift",
        )

        record = log.get_experiment(exp_id)
        assert record is not None
        assert record["dataset_hash"] == "dataset-hash"
        assert record["feature_recipe_hash"] == "feature-hash"
        assert "LightGBM" in record["decision_memo"]

    def test_compare_extracts_changed_and_same_dimensions(self, tmp_path):
        log = _log(tmp_path)
        exp_1 = log.log_experiment(
            project_id="proj-1",
            model_type="random_forest",
            task_type="classification",
            metrics={"f1": 0.7},
            dataset_hash="same-data",
            feature_recipe_hash="feat-a",
            evaluation_set="holdout-v1",
        )
        exp_2 = log.log_experiment(
            project_id="proj-1",
            model_type="lightgbm",
            task_type="classification",
            metrics={"f1": 0.8},
            dataset_hash="same-data",
            feature_recipe_hash="feat-b",
            evaluation_set="holdout-v1",
        )

        diff = ExperimentComparer(log).compare(exp_1, exp_2)
        assert "dataset" in diff.same
        assert "eval_set" in diff.same
        assert "features" in diff.changed
        assert "model" in diff.changed

    def test_get_tree_returns_children(self, tmp_path):
        log = _log(tmp_path)
        parent = log.log_experiment(
            project_id="proj-1",
            model_type="baseline",
            task_type="classification",
            metrics={"f1": 0.6},
        )
        child_1 = log.log_experiment(
            project_id="proj-1",
            model_type="rf",
            task_type="classification",
            metrics={"f1": 0.7},
            parent_experiment_id=parent,
        )
        child_2 = log.log_experiment(
            project_id="proj-1",
            model_type="lgbm",
            task_type="classification",
            metrics={"f1": 0.8},
            parent_experiment_id=parent,
        )

        tree = ExperimentComparer(log).get_tree(parent)
        child_ids = {node.experiment_id for node in tree.children}
        assert child_ids == {child_1, child_2}
