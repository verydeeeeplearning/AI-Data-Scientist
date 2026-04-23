from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ds_agent.application.ports.run_diff_support import MetricDirectionLabel
from ds_agent.application.services.run_diff_usecases import CompareRunsUseCase, RunDiffEngine
from ds_agent.domain.entities.experiment import ExperimentRun
from ds_agent.domain.entities.review_artifact import build_review_artifact


def _run(run_id: str, **overrides: object) -> ExperimentRun:
    payload: dict[str, object] = {
        "run_id": run_id,
        "experiment_group": "exp_churn",
        "sequence": 1,
        "hypothesis": {
            "statement": "Baseline hypothesis",
            "rationale": "Need a reproducible baseline.",
            "expected_effect": "f1_macro tracked",
        },
        "method": {
            "model_family": "lightgbm",
            "hyperparameters": {
                "learning_rate": 0.05,
                "tree": {"max_depth": 6},
            },
            "random_seed": 42,
            "code_ref": "git:aaa111",
        },
        "feature_refs": [{"feature_id": "f_user_activity_30d", "version": 1}],
        "data_snapshot_uri": "snapshot://warehouse/churn/2026-04-07",
        "result": {
            "metrics": {
                "f1_macro": 0.79,
                "auc": 0.85,
                "fp_rate": 0.12,
            },
            "plots": ["artifacts/roc_curve_champion.png"],
        },
        "verifier_summary": {
            "statistical": "PASS",
            "data": "PASS",
            "policy": "WARN",
        },
        "verifier_findings": ["policy.missing_rollback"],
        "review_artifacts": [
            build_review_artifact(
                skill_name="retrain-vs-rollback",
                summary="Keep the baseline until the rollout plan is ready.",
                artifact={
                    "recommendation": "hold",
                    "rationale": "Rollback plan is incomplete.",
                    "evidence": ["policy.missing_rollback"],
                },
            ).model_dump(mode="json")
        ],
        "created_at": datetime(2026, 4, 16, tzinfo=UTC),
        "owner": "growth-ds",
        "status": "succeeded",
    }
    payload.update(overrides)
    return ExperimentRun.model_validate(payload)


@dataclass
class StubRunReader:
    runs: dict[str, ExperimentRun]

    def get_run(self, run_id: str) -> ExperimentRun | None:
        run = self.runs.get(run_id)
        return run.model_copy(deep=True) if run is not None else None


@dataclass
class StubMetricDirections:
    mapping: dict[str, MetricDirectionLabel]

    def direction_for(self, metric_name: str) -> MetricDirectionLabel:
        return self.mapping.get(metric_name, "higher_is_better")


def test_compare_runs_computes_feature_config_metric_and_verifier_diffs() -> None:
    run_a = _run("run-a")
    run_b = _run(
        "run-b",
        sequence=2,
        hypothesis={
            "statement": "Candidate uplift with new feature mix",
            "rationale": "Trade additional variance for stronger recall under the updated feature set.",
            "expected_effect": "f1_macro and recall improve together.",
        },
        method={
            "model_family": "lightgbm",
            "hyperparameters": {
                "learning_rate": 0.03,
                "tree": {"max_depth": 8},
                "l2_leaf_reg": 1.5,
            },
            "random_seed": 42,
            "code_ref": "git:bbb222",
        },
        feature_refs=[
            {"feature_id": "f_user_activity_30d", "version": 2},
            {"feature_id": "f_campaign_exposure", "version": 1},
        ],
        result={
            "metrics": {
                "f1_macro": 0.83,
                "auc": 0.88,
                "fp_rate": 0.09,
            },
            "plots": ["artifacts/roc_curve_candidate.png", "artifacts/pr_curve_candidate.png"],
        },
        verifier_summary={
            "statistical": "PASS",
            "data": "PASS",
            "policy": "PASS",
        },
        verifier_findings=["policy.rollback_plan_validated"],
        review_artifacts=[
            build_review_artifact(
                skill_name="retrain-vs-rollback",
                summary="Rollback is no longer needed; the candidate is stable enough to retrain.",
                artifact={
                    "recommendation": "retrain",
                    "rationale": "Metric uplift offsets the remaining deployment risk.",
                    "evidence": ["f1_macro=0.83", "fp_rate=0.09"],
                },
            ).model_dump(mode="json")
        ],
    )
    use_case = CompareRunsUseCase(
        RunDiffEngine(
            StubRunReader({"run-a": run_a, "run-b": run_b}),
            StubMetricDirections({"fp_rate": "lower_is_better"}),
        )
    )

    diff = use_case.execute("run-a", "run-b")

    assert [(ref.feature_id, ref.version) for ref in diff.feature_set.added] == [
        ("f_campaign_exposure", 1)
    ]
    assert diff.feature_set.version_changed == [("f_user_activity_30d", 1, 2)]
    assert diff.config.changed["hyperparameters.learning_rate"] == (0.05, 0.03)
    assert diff.config.changed["hyperparameters.tree.max_depth"] == (6, 8)
    assert diff.config.added["hyperparameters.l2_leaf_reg"] == 1.5
    metric_directions = {delta.metric: delta.direction for delta in diff.metrics}
    assert metric_directions["f1_macro"] == "better"
    assert metric_directions["auc"] == "better"
    assert metric_directions["fp_rate"] == "better"
    assert {delta.metric for delta in diff.metrics if delta.highlighted} == {
        "f1_macro",
        "fp_rate",
    }
    assert any(delta.significance_note for delta in diff.metrics if delta.highlighted)
    assert {entry.key for entry in diff.artifacts} == {
        "plot:artifacts/pr_curve_candidate.png",
        "plot:artifacts/roc_curve_candidate.png",
        "plot:artifacts/roc_curve_champion.png",
        "review:retrain-vs-rollback",
    }
    assert [entry.key for entry in diff.decisions] == [
        "hypothesis",
        "feature-strategy",
        "model-strategy",
        "verifier",
        "review-artifact:retrain-vs-rollback",
    ]
    assert diff.verifier.policy == ("WARN", "PASS")
    assert diff.verifier.new_findings == ["policy.rollback_plan_validated"]
    assert diff.verifier.resolved_findings == ["policy.missing_rollback"]
    assert "## Artifact Diff" in diff.summary_markdown
    assert "## Decision Trace" in diff.summary_markdown
    assert "Run Diff: run-b vs run-a" in diff.summary_markdown


def test_compare_runs_raises_when_run_is_missing() -> None:
    use_case = CompareRunsUseCase(RunDiffEngine(StubRunReader({}), StubMetricDirections({})))

    try:
        use_case.execute("missing-a", "missing-b")
    except LookupError as exc:
        assert "missing-a" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected LookupError for missing run")
