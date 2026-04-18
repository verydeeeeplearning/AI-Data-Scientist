from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.domain.entities.experiment import ExperimentRun
from ds_agent.domain.entities.review_artifact import build_review_artifact
from ds_agent.memory.experiment_log import ExperimentLog


def _log(tmp_path) -> ExperimentLog:
    return ExperimentLog(data_dir=str(tmp_path / "exp"))


def _extended_run(**overrides: object) -> ExperimentRun:
    payload: dict[str, object] = {
        "run_id": "run-churn-003",
        "experiment_group": "exp_churn",
        "sequence": 3,
        "hypothesis": {
            "statement": "Recency features improve churn recall.",
            "rationale": "Recent activity contains useful signal.",
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
        },
        "feature_refs": [
            {"feature_id": "f_user_activity_30d", "version": 2},
            {"feature_id": "f_campaign_exposure", "version": 1},
        ],
        "data_snapshot_uri": "snapshot://warehouse/churn/2026-04-07",
        "result": {"metrics": {"f1_macro": 0.83, "auc": 0.88}},
        "verifier_report_id": "VR-100",
        "verifier_summary": {"statistical": "PASS", "policy": "PASS"},
        "created_at": datetime(2026, 4, 16, tzinfo=UTC),
        "owner": "growth-ds",
        "status": "succeeded",
        "promotion_state": "candidate",
        "reproducibility_status": "reproduced",
    }
    payload.update(overrides)
    return ExperimentRun.model_validate(payload)


def test_record_extended_round_trips_into_typed_run_and_diffable(tmp_path) -> None:
    log = _log(tmp_path)
    run = _extended_run()

    run_id = log.record_extended(run)
    loaded = log.get_run(run_id)
    diffable = log.to_diffable(run_id)

    assert loaded is not None
    assert loaded.run_id == run.run_id
    assert loaded.method.model_family == "lightgbm"
    assert loaded.feature_refs[0].version == 2
    assert diffable is not None
    assert diffable.feature_set["f_user_activity_30d"] == 2
    assert diffable.verifier_summary == {"statistical": "PASS", "policy": "PASS"}


def test_get_run_normalizes_legacy_record_into_decision_os_shape(tmp_path) -> None:
    log = _log(tmp_path)
    exp_id = log.log_experiment(
        project_id="proj-1",
        model_type="random_forest",
        task_type="classification",
        metrics={"f1": 0.71},
        features=["f_old_login_count", "f_age_bucket"],
        dataset_hash="dataset-hash",
        seed=7,
        notes="Legacy baseline",
    )

    run = log.get_run(exp_id)

    assert run is not None
    assert run.experiment_group == "proj-1"
    assert run.method.model_family == "random_forest"
    assert run.data_snapshot_uri == "dataset-hash"
    assert [ref.feature_id for ref in run.feature_refs] == [
        "f_old_login_count",
        "f_age_bucket",
    ]
    assert run.reproducibility_status == "unknown"


def test_list_runs_filters_by_group_owner_and_status(tmp_path) -> None:
    log = _log(tmp_path)
    log.record_extended(_extended_run())
    log.record_extended(
        _extended_run(
            run_id="run-churn-004",
            sequence=4,
            owner="mlops",
            status="failed",
        )
    )

    succeeded = log.list_runs("exp_churn", owner="growth-ds", status="succeeded")

    assert [run.run_id for run in succeeded] == ["run-churn-003"]


def test_upsert_review_artifact_persists_structured_payload(tmp_path) -> None:
    log = _log(tmp_path)
    log.record_extended(_extended_run())

    artifact = build_review_artifact(
        skill_name="backtesting",
        summary="Backtest stability is acceptable across the last four folds.",
        artifact={
            "folds": [
                {
                    "fold_label": "2026-W14",
                    "metric": "f1_macro",
                    "score": 0.81,
                    "baseline_score": 0.77,
                    "status": "pass",
                },
                {
                    "fold_label": "2026-W15",
                    "metric": "f1_macro",
                    "score": 0.79,
                    "baseline_score": 0.78,
                    "status": "warn",
                },
            ],
            "consistency_score": 0.84,
            "warnings": ["One fold regressed slightly versus baseline."],
        },
        narrative="The model remains stable, but one recent fold softened.",
    )

    updated = log.upsert_review_artifact("run-churn-003", artifact)
    loaded = log.get_run("run-churn-003")

    assert updated.review_artifacts[0].skill_name == "backtesting"
    assert loaded is not None
    assert loaded.review_artifacts[0].artifact.artifact_type == "backtesting"
    assert loaded.review_artifacts[0].artifact.folds[1].status == "warn"
