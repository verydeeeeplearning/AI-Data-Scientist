from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from ds_agent.domain.entities.experiment import ExperimentRun
from ds_agent.domain.entities.feature import Feature, FeatureStatistics
from ds_agent.domain.entities.model import Model
from ds_agent.domain.entities.post_deploy import PostDeploySnapshot
from ds_agent.infrastructure.decision_os_container import build_decision_os_container
from ds_agent.infrastructure.persistence.deploy_monitor_state_store import (
    SqliteDeployMonitorStateStore,
)
from ds_agent.infrastructure.persistence.feature_registry_store import SqliteFeatureRegistryStore
from ds_agent.infrastructure.persistence.model_registry_store import SqliteModelRegistryStore
from ds_agent.memory.experiment_log import ExperimentLog
from ds_agent.tools.registry import ToolRegistry


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
            "hyperparameters": {"learning_rate": 0.05},
            "random_seed": 42,
            "code_ref": "git:aaa111",
        },
        "feature_refs": [{"feature_id": "f_user_activity_30d", "version": 1}],
        "data_snapshot_uri": "snapshot://warehouse/churn/2026-04-07",
        "result": {"metrics": {"f1_macro": 0.79, "fp_rate": 0.12}},
        "verifier_summary": {
            "statistical": "PASS",
            "data": "PASS",
            "policy": "WARN",
        },
        "verifier_findings": ["policy.missing_rollback"],
        "created_at": datetime(2026, 4, 16, tzinfo=UTC),
        "owner": "growth-ds",
        "status": "succeeded",
    }
    payload.update(overrides)
    return ExperimentRun.model_validate(payload)


@dataclass
class StubMetricRepository:
    def get(self, metric_id: str):
        return None

    def resolve(self, query: str, *, grain=None, limit: int = 5):
        return []

    def save(self, metric) -> None:
        return None


class StubSnapshotProvider:
    def __init__(self, snapshot: PostDeploySnapshot | None) -> None:
        self._snapshot = snapshot

    def load(self, model_id: str, model_version: int) -> PostDeploySnapshot | None:
        del model_id, model_version
        return self._snapshot.model_copy(deep=True) if self._snapshot is not None else None


def _feature(alias: str = "stable") -> Feature:
    return Feature.model_validate(
        {
            "feature_id": "f_user_activity_30d",
            "display_name": "User Activity 30d",
            "version": 1,
            "description": "Rolling 30 day user activity score.",
            "transformation_logic": "SELECT * FROM growth.user_logins",
            "source_tables": ["growth.user_logins"],
            "owner": "growth-ds",
            "created_at": datetime(2026, 4, 16, tzinfo=UTC),
            "statistics": FeatureStatistics(
                mean=1.2,
                median=1.0,
                p95=2.5,
                null_rate=0.01,
                distinct_count=50,
                last_computed_at=datetime(2026, 4, 16, tzinfo=UTC),
            ),
            "point_in_time_safe": True,
            "alias": alias,
        }
    )


def _model(lineage_run_id: str = "run-a", alias: str = "champion") -> Model:
    return Model.model_validate(
        {
            "model_id": "m_churn_lightgbm",
            "version": 5,
            "alias": alias,
            "lineage_run_id": lineage_run_id,
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
                "feature_refs": [{"feature_id": "f_user_activity_30d", "version": 1}],
            },
            "created_at": datetime(2026, 4, 16, tzinfo=UTC),
            "description": "Champion churn model.",
        }
    )


def _snapshot(reference_path: str, current_path: str) -> PostDeploySnapshot:
    return PostDeploySnapshot.model_validate(
        {
            "reference_path": reference_path,
            "current_path": current_path,
            "current_metrics": {"f1_macro": 0.66, "fp_rate": 0.16},
            "latency_p95_ms": 140.0,
            "qps": 30.0,
            "observed_at": datetime(2026, 4, 16, 12, tzinfo=UTC),
        }
    )


@pytest.fixture
def decision_os_tool_module(tmp_path):
    ToolRegistry.reset()
    module_name = "ds_agent.tools.decision_os_tools"
    if module_name in sys.modules:
        module = importlib.reload(sys.modules[module_name])
    else:
        module = importlib.import_module(module_name)

    log = ExperimentLog(data_dir=str(tmp_path / "exp"))
    log.record_extended(_run("run-a"))
    log.record_extended(
        _run(
            "run-b",
            sequence=2,
            method={
                "model_family": "lightgbm",
                "hyperparameters": {"learning_rate": 0.03},
                "random_seed": 42,
                "code_ref": "git:bbb222",
            },
            feature_refs=[
                {"feature_id": "f_user_activity_30d", "version": 2},
                {"feature_id": "f_campaign_exposure", "version": 1},
            ],
            result={"metrics": {"f1_macro": 0.83, "fp_rate": 0.09}},
            verifier_summary={
                "statistical": "PASS",
                "data": "PASS",
                "policy": "PASS",
            },
            verifier_findings=["policy.rollback_plan_validated"],
        )
    )
    module.set_decision_os_container(
        build_decision_os_container(
            experiment_log=log,
            metric_repo=StubMetricRepository(),
        )
    )
    return module


@pytest.fixture
def decision_os_promotion_tool_module(tmp_path):
    ToolRegistry.reset()
    module_name = "ds_agent.tools.decision_os_tools"
    if module_name in sys.modules:
        module = importlib.reload(sys.modules[module_name])
    else:
        module = importlib.import_module(module_name)

    log = ExperimentLog(data_dir=str(tmp_path / "exp"))
    log.record_extended(_run("run-a", result={"metrics": {"f1_macro": 0.79, "fp_rate": 0.12}}))
    log.record_extended(
        _run(
            "run-b",
            sequence=2,
            result={"metrics": {"f1_macro": 0.83, "fp_rate": 0.09}},
            verifier_summary={
                "statistical": "PASS",
                "data": "PASS",
                "policy": "PASS",
            },
            reproducibility_status="reproduced",
        )
    )

    feature_store = SqliteFeatureRegistryStore(tmp_path / "decision_os" / "feature_registry.db")
    feature_store.save(_feature())

    model_store = SqliteModelRegistryStore(tmp_path / "decision_os" / "model_registry.db")
    model_store.save(_model(lineage_run_id="run-a"))

    rollback_plan = tmp_path / "rollback_plan.yaml"
    rollback_plan.write_text(
        "\n".join(
            [
                "previous_champion_model_id: m_churn_lightgbm",
                "traffic_shift_procedure: Shift traffic back over 10 minutes.",
                "health_check_queries:",
                "  - SELECT 1",
                "estimated_rollback_time_sec: 600",
                "owner: mlops",
            ]
        ),
        encoding="utf-8",
    )

    module.set_decision_os_container(
        build_decision_os_container(
            experiment_log=log,
            feature_store=feature_store,
            model_store=model_store,
            metric_repo=StubMetricRepository(),
            workspace_dir=str(tmp_path),
        )
    )
    return module, rollback_plan


@pytest.fixture
def decision_os_monitor_tool_module(tmp_path):
    ToolRegistry.reset()
    module_name = "ds_agent.tools.decision_os_tools"
    if module_name in sys.modules:
        module = importlib.reload(sys.modules[module_name])
    else:
        module = importlib.import_module(module_name)

    log = ExperimentLog(data_dir=str(tmp_path / "exp"))
    log.record_extended(_run("run-a", result={"metrics": {"f1_macro": 0.80, "fp_rate": 0.12}}))

    feature_store = SqliteFeatureRegistryStore(tmp_path / "decision_os" / "feature_registry.db")
    feature_store.save(_feature())

    model_store = SqliteModelRegistryStore(tmp_path / "decision_os" / "model_registry.db")
    model_store.save(_model(lineage_run_id="run-a"))

    state_store = SqliteDeployMonitorStateStore(tmp_path / "decision_os" / "deploy_monitor.db")
    reference_path = tmp_path / "reference.csv"
    current_path = tmp_path / "current.csv"
    reference_path.write_text("f_user_activity_30d\n0\n0\n0\n0\n0\n", encoding="utf-8")
    current_path.write_text("f_user_activity_30d\n10\n10\n10\n10\n10\n", encoding="utf-8")

    container = build_decision_os_container(
        experiment_log=log,
        feature_store=feature_store,
        model_store=model_store,
        deploy_monitor_store=state_store,
        metric_repo=StubMetricRepository(),
        snapshot_provider=StubSnapshotProvider(_snapshot(str(reference_path), str(current_path))),
        workspace_dir=str(tmp_path),
    )
    container.post_deploy_monitor.periodic_sweep()
    module.set_decision_os_container(container)
    return module


@pytest.mark.asyncio
async def test_compare_runs_tool_happy_path(decision_os_tool_module) -> None:
    result = json.loads(
        await ToolRegistry.dispatch(
            "compare_runs",
            {"run_a_id": "run-a", "run_b_id": "run-b"},
        )
    )

    assert result["ok"] is True
    assert result["run_a_id"] == "run-a"
    assert result["run_b_id"] == "run-b"
    assert result["feature_set"]["version_changed"] == [["f_user_activity_30d", 1, 2]]
    assert result["verifier"]["policy"] == ["WARN", "PASS"]


@pytest.mark.asyncio
async def test_compare_runs_tool_returns_not_found(decision_os_tool_module) -> None:
    result = json.loads(
        await ToolRegistry.dispatch(
            "compare_runs",
            {"run_a_id": "missing-a", "run_b_id": "missing-b"},
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "RUN_NOT_FOUND"


@pytest.mark.asyncio
async def test_request_promotion_tool_happy_path(decision_os_promotion_tool_module) -> None:
    _, rollback_plan = decision_os_promotion_tool_module

    result = json.loads(
        await ToolRegistry.dispatch(
            "request_promotion",
            {
                "candidate_run_id": "run-b",
                "target_stage": "production",
                "approvers": ["ds-user", "lead-user", "mlops-user"],
                "rollback_plan_ref": str(rollback_plan),
            },
        )
    )

    assert result["ok"] is True
    assert result["candidate_run_id"] == "run-b"
    assert result["chain_state"] == "pending_DS"
    checks = {check["name"]: check["status"] for check in result["policy_checks"]}
    assert checks["metric_vs_baseline"] == "pass"
    assert checks["rollback_plan"] == "pass"


@pytest.mark.asyncio
async def test_request_promotion_tool_returns_not_found(
    decision_os_promotion_tool_module,
) -> None:
    _, rollback_plan = decision_os_promotion_tool_module

    result = json.loads(
        await ToolRegistry.dispatch(
            "request_promotion",
            {
                "candidate_run_id": "missing-run",
                "target_stage": "production",
                "approvers": ["ds-user", "lead-user", "mlops-user"],
                "rollback_plan_ref": str(rollback_plan),
            },
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "RUN_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_post_deploy_status_tool_happy_path(
    decision_os_monitor_tool_module,
) -> None:
    result = json.loads(
        await ToolRegistry.dispatch(
            "get_post_deploy_status",
            {"model_id": "m_churn_lightgbm", "window": "7d"},
        )
    )

    assert result["ok"] is True
    assert result["model_id"] == "m_churn_lightgbm"
    assert result["summary"]["overall_status"] == "alert"
    assert result["alerts"]


@pytest.mark.asyncio
async def test_get_post_deploy_status_tool_returns_not_found(
    decision_os_monitor_tool_module,
) -> None:
    result = json.loads(
        await ToolRegistry.dispatch(
            "get_post_deploy_status",
            {"model_id": "missing-model", "window": "7d"},
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "STATUS_NOT_FOUND"


@pytest.mark.asyncio
async def test_record_review_artifact_tool_happy_path(decision_os_tool_module) -> None:
    result = json.loads(
        await ToolRegistry.dispatch(
            "record_review_artifact",
            {
                "run_id": "run-b",
                "skill_name": "retrain-vs-rollback",
                "summary": "Rollback is safer than retrain for this incident.",
                "artifact": {
                    "recommendation": "rollback",
                    "rationale": "Drift and precision loss exceed the rollback threshold.",
                    "evidence": ["psi=0.31", "precision=-0.08"],
                },
                "narrative": "The latest deployment should be rolled back immediately.",
            },
        )
    )

    assert result["ok"] is True
    assert result["run_id"] == "run-b"
    assert result["review_artifact_count"] == 1
    assert result["review_artifacts"][0]["skill_name"] == "retrain-vs-rollback"


@pytest.mark.asyncio
async def test_get_review_artifacts_tool_happy_path(decision_os_tool_module) -> None:
    await ToolRegistry.dispatch(
        "record_review_artifact",
        {
            "run_id": "run-b",
            "skill_name": "uncertainty-quantification",
            "summary": "The confidence interval remains inside the allowed band.",
            "artifact": {
                "methodology": "bootstrap",
                "intervals": [
                    {
                        "metric": "f1_macro",
                        "lower": 0.80,
                        "upper": 0.86,
                        "confidence_level": 0.95,
                    }
                ],
                "warnings": [],
            },
        },
    )

    result = json.loads(
        await ToolRegistry.dispatch(
            "get_review_artifacts",
            {"run_id": "run-b"},
        )
    )

    assert result["ok"] is True
    assert result["review_artifact_count"] == 1
    assert result["review_artifacts"][0]["artifact"]["artifact_type"] == (
        "uncertainty-quantification"
    )
