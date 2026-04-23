from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from ds_agent.application.services.promotion_gate_usecases import (
    AutoRollbackUseCase,
    PromotionGate,
)
from ds_agent.domain.entities.experiment import ExperimentRun
from ds_agent.domain.entities.feature import FeatureRef
from ds_agent.domain.entities.model import Model
from ds_agent.domain.entities.post_deploy import PostDeploySnapshot
from ds_agent.domain.entities.promotion import PromotionDecision
from ds_agent.infrastructure.importers.yaml_rollback_plan_loader import (
    YamlRollbackPlanLoader,
)
from ds_agent.infrastructure.persistence.deploy_monitor_state_store import (
    SqliteDeployMonitorStateStore,
)
from ds_agent.infrastructure.persistence.model_registry_store import SqliteModelRegistryStore
from ds_agent.infrastructure.persistence.promotion_decision_store import (
    SqlitePromotionDecisionStore,
)
from ds_agent.memory.experiment_log import ExperimentLog
from ds_agent.runtime.post_deploy_monitor import (
    ExperimentLogAutoRetrainExecutor,
    PostDeployMonitor,
    PromotionGateAutoRollbackExecutor,
    StaticPostDeployAutomationPolicyResolver,
)
from ds_agent.runtime.runtime_event_log import RuntimeEventLog


def _run(run_id: str, **overrides: object) -> ExperimentRun:
    payload: dict[str, object] = {
        "run_id": run_id,
        "experiment_group": "exp_churn",
        "sequence": 1,
        "hypothesis": {
            "statement": "Champion baseline",
            "rationale": "Current production baseline.",
            "expected_effect": "f1_macro tracked",
        },
        "method": {
            "model_family": "lightgbm",
            "hyperparameters": {"learning_rate": 0.05},
            "random_seed": 42,
            "code_ref": "git:aaa111",
        },
        "feature_refs": [{"feature_id": "f_user_activity_30d", "version": 1}],
        "data_snapshot_uri": "snapshot://warehouse/churn/2026-04-07",
        "result": {"metrics": {"f1_macro": 0.80, "fp_rate": 0.12}},
        "created_at": datetime(2026, 4, 16, tzinfo=UTC),
        "owner": "growth-ds",
        "status": "succeeded",
    }
    payload.update(overrides)
    return ExperimentRun.model_validate(payload)


def _model(alias: str = "champion", **overrides: object) -> Model:
    payload: dict[str, object] = {
        "model_id": "m_churn_lightgbm",
        "version": 5,
        "alias": alias,
        "lineage_run_id": "run-champion",
        "artifact": {
            "uri": "model://churn/lightgbm/v5",
            "format": "json",
            "size_bytes": 1024,
            "checksum": "abc123",
        },
        "serving": {
            "runtime": "batch",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "feature_refs": [FeatureRef(feature_id="f_user_activity_30d", version=1)],
            "latency_budget_ms": 100,
            "throughput_budget_qps": 40,
        },
        "created_at": datetime(2026, 4, 16, tzinfo=UTC),
        "description": "Champion churn model.",
    }
    payload.update(overrides)
    return Model.model_validate(payload)


@dataclass
class StubMetricDirections:
    mapping: dict[str, str]

    def direction_for(self, metric_name: str) -> str:
        return self.mapping.get(metric_name, "higher_is_better")


@dataclass
class StubSnapshotProvider:
    snapshot: PostDeploySnapshot | None

    def load(self, model_id: str, model_version: int) -> PostDeploySnapshot | None:
        del model_id, model_version
        return self.snapshot.model_copy(deep=True) if self.snapshot is not None else None


class UnusedFeatureStore:
    def get(self, feature_id: str, version: int):
        del feature_id, version
        return None

    def get_latest(self, feature_id: str):
        del feature_id
        return None

    def list_versions(self, feature_id: str):
        del feature_id
        return []

    def list_features(self, *, alias=None, limit: int = 100):
        del alias, limit
        return []

    def save(self, feature) -> None:
        del feature

    def list_experiments_using(self, feature_id: str):
        del feature_id
        return []

    def list_by_source_table(self, source_table: str):
        del source_table
        return []


def test_post_deploy_monitor_sweep_persists_state_and_emits_alert(tmp_path) -> None:
    experiment_log = ExperimentLog(data_dir=str(tmp_path / "exp"))
    experiment_log.record_extended(_run("run-champion"))

    model_store = SqliteModelRegistryStore(tmp_path / "decision_os" / "model_registry.db")
    model_store.save(_model())

    reference_path = tmp_path / "reference.csv"
    current_path = tmp_path / "current.csv"
    reference_path.write_text("f_user_activity_30d\n0\n0\n0\n0\n0\n", encoding="utf-8")
    current_path.write_text("f_user_activity_30d\n10\n10\n10\n10\n10\n", encoding="utf-8")

    snapshot = PostDeploySnapshot.model_validate(
        {
            "reference_path": str(reference_path),
            "current_path": str(current_path),
            "current_metrics": {"f1_macro": 0.66, "fp_rate": 0.16},
            "latency_p95_ms": 140.0,
            "qps": 30.0,
            "observed_at": datetime(2026, 4, 16, 12, tzinfo=UTC),
        }
    )
    state_store = SqliteDeployMonitorStateStore(tmp_path / "decision_os" / "deploy_monitor.db")
    event_log = RuntimeEventLog(base_dir=tmp_path / "runtime")
    monitor = PostDeployMonitor(
        experiment_runs=experiment_log,
        models=model_store,
        state_store=state_store,
        snapshot_provider=StubSnapshotProvider(snapshot),
        event_log=event_log,
        metric_directions=StubMetricDirections({"fp_rate": "lower_is_better"}),
    )

    states = monitor.periodic_sweep()

    assert len(states) == 1
    state = states[0]
    assert state.model_id == "m_churn_lightgbm"
    assert state.overall_status == "alert"
    assert state.remediation.decision == "rollback"
    assert state.drift.max_psi is not None
    assert state.drift.max_psi > 0.3
    assert state.alerts

    stored = state_store.latest("m_churn_lightgbm")
    assert stored is not None
    assert stored.state_id == state.state_id

    events = event_log.list(limit=5, category="deployment")
    assert len(events) == 1
    assert events[0].kind == "post_deploy_alert"
    assert "rollback" in json.dumps(events[0].metadata)


def test_post_deploy_monitor_skips_models_without_snapshots(tmp_path) -> None:
    experiment_log = ExperimentLog(data_dir=str(tmp_path / "exp"))
    experiment_log.record_extended(_run("run-champion"))

    model_store = SqliteModelRegistryStore(tmp_path / "decision_os" / "model_registry.db")
    model_store.save(_model())

    monitor = PostDeployMonitor(
        experiment_runs=experiment_log,
        models=model_store,
        state_store=SqliteDeployMonitorStateStore(tmp_path / "decision_os" / "deploy_monitor.db"),
        snapshot_provider=StubSnapshotProvider(None),
        event_log=RuntimeEventLog(base_dir=tmp_path / "runtime"),
        metric_directions=StubMetricDirections({"fp_rate": "lower_is_better"}),
    )

    assert monitor.periodic_sweep() == []


def test_post_deploy_monitor_auto_retrain_creates_candidate_run(tmp_path) -> None:
    experiment_log = ExperimentLog(data_dir=str(tmp_path / "exp"))
    experiment_log.record_extended(_run("run-champion"))

    model_store = SqliteModelRegistryStore(tmp_path / "decision_os" / "model_registry.db")
    model_store.save(_model())

    reference_path = tmp_path / "reference.csv"
    current_path = tmp_path / "current.csv"
    reference_path.write_text("f_user_activity_30d\n0\n0\n0\n0\n0\n", encoding="utf-8")
    current_path.write_text("f_user_activity_30d\n10\n10\n10\n10\n10\n", encoding="utf-8")

    snapshot = PostDeploySnapshot.model_validate(
        {
            "reference_path": str(reference_path),
            "current_path": str(current_path),
            "current_metrics": {"f1_macro": 0.75, "fp_rate": 0.13},
            "latency_p95_ms": 90.0,
            "qps": 45.0,
            "observed_at": datetime(2026, 4, 16, 13, tzinfo=UTC),
        }
    )
    event_log = RuntimeEventLog(base_dir=tmp_path / "runtime")
    monitor = PostDeployMonitor(
        experiment_runs=experiment_log,
        models=model_store,
        state_store=SqliteDeployMonitorStateStore(tmp_path / "decision_os" / "deploy_monitor.db"),
        snapshot_provider=StubSnapshotProvider(snapshot),
        event_log=event_log,
        metric_directions=StubMetricDirections({"fp_rate": "lower_is_better"}),
        trigger_policy=StaticPostDeployAutomationPolicyResolver(trigger_mode="auto_retrain"),
        auto_retrain_executor=ExperimentLogAutoRetrainExecutor(experiment_log),
    )

    states = monitor.periodic_sweep()

    assert states[0].trigger_mode == "auto_retrain"
    assert states[0].trigger_payload["executed"] is True
    created_run_id = states[0].trigger_payload["execution"]["created_run_id"]
    created_run = experiment_log.get_run(created_run_id)
    assert created_run is not None
    assert created_run.promotion_state == "candidate"
    assert created_run.status == "running"

    events = event_log.list(limit=10, category="deployment")
    assert any(event.kind == "post_deploy_auto_retrain_requested" for event in events)


def test_post_deploy_monitor_auto_rollback_executes_and_restores_previous_champion(
    tmp_path,
) -> None:
    experiment_log = ExperimentLog(data_dir=str(tmp_path / "exp"))
    experiment_log.record_extended(_run("run-candidate"))

    model_store = SqliteModelRegistryStore(tmp_path / "decision_os" / "model_registry.db")
    model_store.save(_model(model_id="m_churn_lightgbm", lineage_run_id="run-candidate"))
    model_store.save(
        _model(
            model_id="m_churn_xgboost",
            version=4,
            alias="retired",
            lineage_run_id="run-legacy",
            artifact={
                "uri": "model://churn/xgboost/v4",
                "format": "json",
                "size_bytes": 2048,
                "checksum": "legacy",
            },
        )
    )

    reference_path = tmp_path / "reference.csv"
    current_path = tmp_path / "current.csv"
    reference_path.write_text("f_user_activity_30d\n0\n0\n0\n0\n0\n", encoding="utf-8")
    current_path.write_text("f_user_activity_30d\n10\n10\n10\n10\n10\n", encoding="utf-8")
    rollback_plan = tmp_path / "rollback_plan.yaml"
    rollback_plan.write_text(
        "\n".join(
            [
                "previous_champion_model_id: m_churn_xgboost",
                "traffic_shift_procedure: Shift traffic back over 10 minutes.",
                "health_check_queries:",
                "  - SELECT 1",
                "estimated_rollback_time_sec: 600",
                "owner: mlops",
            ]
        ),
        encoding="utf-8",
    )

    decision_store = SqlitePromotionDecisionStore(tmp_path / "decision_os" / "promotion_gate.db")
    decision_store.save(
        PromotionDecision.model_validate(
            {
                "decision_id": "promotion-001",
                "candidate_run_id": "run-candidate",
                "candidate_model_id": "m_churn_lightgbm",
                "target_stage": "production",
                "policy_checks": [],
                "approvals": [],
                "chain_state": "approved",
                "rollback_plan_ref": str(rollback_plan),
                "created_at": datetime(2026, 4, 16, 10, tzinfo=UTC),
            }
        )
    )
    gate = PromotionGate(
        experiment_runs=experiment_log,
        features=UnusedFeatureStore(),
        models=model_store,
        decisions=decision_store,
        rollback_plans=YamlRollbackPlanLoader(tmp_path),
        metric_directions=StubMetricDirections({"fp_rate": "lower_is_better"}),
    )
    snapshot = PostDeploySnapshot.model_validate(
        {
            "reference_path": str(reference_path),
            "current_path": str(current_path),
            "current_metrics": {"f1_macro": 0.66, "fp_rate": 0.16},
            "latency_p95_ms": 140.0,
            "qps": 30.0,
            "observed_at": datetime(2026, 4, 16, 14, tzinfo=UTC),
        }
    )
    event_log = RuntimeEventLog(base_dir=tmp_path / "runtime")
    monitor = PostDeployMonitor(
        experiment_runs=experiment_log,
        models=model_store,
        state_store=SqliteDeployMonitorStateStore(tmp_path / "decision_os" / "deploy_monitor.db"),
        snapshot_provider=StubSnapshotProvider(snapshot),
        event_log=event_log,
        metric_directions=StubMetricDirections({"fp_rate": "lower_is_better"}),
        trigger_policy=StaticPostDeployAutomationPolicyResolver(trigger_mode="auto_rollback"),
        auto_rollback_executor=PromotionGateAutoRollbackExecutor(AutoRollbackUseCase(gate).execute),
    )

    states = monitor.periodic_sweep()

    assert states[0].trigger_mode == "auto_rollback"
    assert states[0].trigger_payload["executed"] is True
    assert model_store.get("m_churn_lightgbm", 5).alias == "retired"
    assert model_store.get("m_churn_xgboost", 4).alias == "champion"

    events = event_log.list(limit=10, category="deployment")
    assert any(event.kind == "post_deploy_auto_rollback_executed" for event in events)
