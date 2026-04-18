"""Utilities for comparing and traversing experiment history."""

from __future__ import annotations

from dataclasses import dataclass, field

from ds_agent.memory.experiment_log import ExperimentLog


@dataclass(frozen=True, slots=True)
class ExperimentDiff:
    """High-level diff between two experiment records."""

    changed: list[str]
    same: list[str]
    first_id: str
    second_id: str


@dataclass(frozen=True, slots=True)
class ExperimentTree:
    """Tree representation of experiment branching."""

    experiment_id: str
    children: list[ExperimentTree] = field(default_factory=list)


class ExperimentComparer:
    """Compare experiment records and reconstruct parent-child trees."""

    def __init__(self, experiment_log: ExperimentLog) -> None:
        self._experiment_log = experiment_log

    def compare(self, exp_id_1: str, exp_id_2: str) -> ExperimentDiff:
        first = self._experiment_log.get_experiment(exp_id_1)
        second = self._experiment_log.get_experiment(exp_id_2)
        if first is None or second is None:
            raise LookupError("Experiment not found for comparison")

        comparable_fields = {
            "dataset": first.get("dataset_hash") == second.get("dataset_hash"),
            "features": first.get("feature_recipe_hash") == second.get("feature_recipe_hash"),
            "model": first.get("model_type") == second.get("model_type")
            and first.get("hyperparameters", {}) == second.get("hyperparameters", {}),
            "eval_set": first.get("evaluation_set") == second.get("evaluation_set"),
        }
        changed = [name for name, same in comparable_fields.items() if not same]
        unchanged = [name for name, same in comparable_fields.items() if same]
        return ExperimentDiff(
            changed=changed,
            same=unchanged,
            first_id=exp_id_1,
            second_id=exp_id_2,
        )

    def get_tree(self, root_experiment_id: str) -> ExperimentTree:
        root = self._experiment_log.get_experiment(root_experiment_id)
        if root is None:
            raise LookupError(f"Experiment not found: {root_experiment_id}")
        children = [
            self.get_tree(child["id"])
            for child in self._experiment_log.get_children(root_experiment_id)
        ]
        return ExperimentTree(experiment_id=root_experiment_id, children=children)
