from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.domain.entities.experiment import ExperimentRun


def test_experiment_run_to_diffable_projects_structured_config() -> None:
    run = ExperimentRun.model_validate(
        {
            "run_id": "run-churn-003",
            "experiment_group": "exp_churn",
            "sequence": 3,
            "hypothesis": {
                "statement": "Recency features improve churn recall.",
                "rationale": "Recent behavior usually dominates churn propensity.",
                "expected_effect": "f1_macro >= 0.82",
            },
            "method": {
                "model_family": "lightgbm",
                "hyperparameters": {"num_leaves": 31, "learning_rate": 0.05},
                "train_window": [
                    "2026-03-01T00:00:00+00:00",
                    "2026-03-31T00:00:00+00:00",
                ],
                "eval_window": [
                    "2026-04-01T00:00:00+00:00",
                    "2026-04-07T00:00:00+00:00",
                ],
                "random_seed": 42,
                "code_ref": "git:abc123",
                "nondeterminism_notes": "none",
            },
            "feature_refs": [
                {"feature_id": "f_user_activity_30d", "version": 2},
                {"feature_id": "f_campaign_exposure", "version": 1},
            ],
            "data_snapshot_uri": "snapshot://warehouse/churn/2026-04-07",
            "result": {"metrics": {"f1_macro": 0.83, "auc": 0.88}},
            "verifier_summary": {"statistical": "PASS", "policy": "WARN"},
            "created_at": datetime(2026, 4, 16, tzinfo=UTC),
            "owner": "growth-ds",
            "status": "succeeded",
        }
    )

    diffable = run.to_diffable()

    assert diffable.feature_set == {
        "f_user_activity_30d": 2,
        "f_campaign_exposure": 1,
    }
    assert diffable.config["model_family"] == "lightgbm"
    assert diffable.config["random_seed"] == 42
    assert diffable.code_ref == "git:abc123"
    assert diffable.metrics["f1_macro"] == 0.83
