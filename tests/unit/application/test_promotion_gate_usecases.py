from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from ds_agent.domain.entities.experiment import ExperimentRun
from ds_agent.domain.entities.feature import Feature, FeatureStatistics
from ds_agent.domain.entities.model import Model
from ds_agent.domain.entities.promotion import PromotionDecision, RollbackPlan


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
        "result": {"metrics": {"f1_macro": 0.82, "fp_rate": 0.11}},
        "verifier_summary": {
            "statistical": "PASS",
            "data": "PASS",
            "policy": "PASS",
        },
        "created_at": datetime(2026, 4, 16, tzinfo=UTC),
        "owner": "growth-ds",
        "status": "succeeded",
        "reproducibility_status": "reproduced",
    }
    payload.update(overrides)
    return ExperimentRun.model_validate(payload)


def _feature(alias: str = "stable", **overrides: object) -> Feature:
    payload: dict[str, object] = {
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
    payload.update(overrides)
    return Feature.model_validate(payload)


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
            "feature_refs": [{"feature_id": "f_user_activity_30d", "version": 1}],
        },
        "created_at": datetime(2026, 4, 16, tzinfo=UTC),
        "description": "Champion churn model.",
    }
    payload.update(overrides)
    return Model.model_validate(payload)


@dataclass
class StubRunReader:
    runs: dict[str, ExperimentRun]

    def get_run(self, run_id: str) -> ExperimentRun | None:
        run = self.runs.get(run_id)
        return run.model_copy(deep=True) if run is not None else None


@dataclass
class StubFeatureStore:
    features: dict[tuple[str, int], Feature]

    def get(self, feature_id: str, version: int) -> Feature | None:
        feature = self.features.get((feature_id, version))
        return feature.model_copy(deep=True) if feature is not None else None

    def get_latest(self, feature_id: str) -> Feature | None:
        matches = [feature for (name, _), feature in self.features.items() if name == feature_id]
        if not matches:
            return None
        return max(matches, key=lambda item: item.version).model_copy(deep=True)

    def list_versions(self, feature_id: str) -> list[Feature]:
        return [
            feature.model_copy(deep=True)
            for feature in sorted(
                (feature for (name, _), feature in self.features.items() if name == feature_id),
                key=lambda item: item.version,
                reverse=True,
            )
        ]

    def list_features(self, *, alias=None, limit: int = 100) -> list[Feature]:
        del alias, limit
        return [feature.model_copy(deep=True) for feature in self.features.values()]

    def save(self, feature: Feature) -> None:
        self.features[(feature.feature_id, feature.version)] = feature.model_copy(deep=True)

    def list_experiments_using(self, feature_id: str) -> list[str]:
        del feature_id
        return []

    def list_by_source_table(self, source_table: str) -> list[Feature]:
        del source_table
        return []


@dataclass
class StubModelRegistry:
    models: dict[tuple[str, int], Model] = field(default_factory=dict)

    def get(self, model_id: str, version: int) -> Model | None:
        model = self.models.get((model_id, version))
        return model.model_copy(deep=True) if model is not None else None

    def get_by_alias(self, alias: str) -> Model | None:
        for model in self.models.values():
            if model.alias == alias:
                return model.model_copy(deep=True)
        return None

    def list_from_run(self, run_id: str) -> list[Model]:
        return [
            model.model_copy(deep=True)
            for model in self.models.values()
            if model.lineage_run_id == run_id
        ]

    def list_models(self, *, alias=None, limit: int = 100) -> list[Model]:
        del alias
        return [model.model_copy(deep=True) for model in list(self.models.values())[:limit]]

    def save(self, model: Model) -> None:
        self.models[(model.model_id, model.version)] = model.model_copy(deep=True)

    def update_alias(
        self,
        model_id: str,
        version: int,
        alias: str,
        *,
        promoted_at: datetime | None = None,
        retired_at: datetime | None = None,
    ) -> None:
        model = self.models[(model_id, version)]
        self.models[(model_id, version)] = model.model_copy(
            update={
                "alias": alias,
                "promoted_at": promoted_at,
                "retired_at": retired_at,
            }
        )


@dataclass
class StubDecisionStore:
    decisions: dict[str, PromotionDecision] = field(default_factory=dict)

    def save(self, decision: PromotionDecision) -> None:
        self.decisions[decision.decision_id] = decision.model_copy(deep=True)

    def get(self, decision_id: str) -> PromotionDecision | None:
        decision = self.decisions.get(decision_id)
        return decision.model_copy(deep=True) if decision is not None else None

    def list_for_model(
        self,
        candidate_model_id: str,
        *,
        limit: int = 20,
    ) -> list[PromotionDecision]:
        return [
            decision.model_copy(deep=True)
            for decision in list(self.decisions.values())[:limit]
            if decision.candidate_model_id == candidate_model_id
        ]


@dataclass
class StubRollbackPlanLoader:
    plans: dict[str, RollbackPlan]
    errors: dict[str, str] = field(default_factory=dict)

    def load(self, source: str) -> RollbackPlan:
        if source in self.errors:
            raise ValueError(self.errors[source])
        plan = self.plans[source]
        return plan.model_copy(deep=True)


@dataclass
class StubMetricDirections:
    mapping: dict[str, str] = field(default_factory=dict)

    def direction_for(self, metric_name: str) -> str:
        return self.mapping.get(metric_name, "higher_is_better")


def _rollback_plan(previous_champion_model_id: str = "m_churn_lightgbm") -> RollbackPlan:
    return RollbackPlan.model_validate(
        {
            "previous_champion_model_id": previous_champion_model_id,
            "traffic_shift_procedure": "Shift traffic back to champion over 10 minutes.",
            "health_check_queries": ["SELECT 1"],
            "estimated_rollback_time_sec": 600,
            "owner": "mlops",
        }
    )


def _build_gate(candidate: ExperimentRun, **kwargs: object):
    from ds_agent.application.services.promotion_gate_usecases import PromotionGate

    champion_run = _run(
        "run-champion",
        result={"metrics": {"f1_macro": 0.80, "fp_rate": 0.12}},
        owner="mlops",
    )
    runs = StubRunReader({"run-champion": champion_run, candidate.run_id: candidate})
    feature_store = kwargs.get("feature_store") or StubFeatureStore(
        {("f_user_activity_30d", 1): _feature()}
    )
    model_registry = kwargs.get("model_registry") or StubModelRegistry(
        {("m_churn_lightgbm", 5): _model()}
    )
    decision_store = kwargs.get("decision_store") or StubDecisionStore()
    rollback_loader = kwargs.get("rollback_loader") or StubRollbackPlanLoader(
        {"rollback_plan.yaml": _rollback_plan()}
    )
    metric_directions = kwargs.get("metric_directions") or StubMetricDirections(
        {"fp_rate": "lower_is_better"}
    )
    return PromotionGate(
        runs,
        feature_store,
        model_registry,
        decision_store,
        rollback_loader,
        metric_directions,
    ), decision_store


def _policy_map(decision: PromotionDecision) -> dict[str, str]:
    return {check.name: check.status for check in decision.policy_checks}


def test_request_promotion_passes_core_checks_and_starts_pending_chain() -> None:
    gate, store = _build_gate(_run("run-candidate"))

    decision = gate.evaluate(
        candidate_run_id="run-candidate",
        target_stage="production",
        approvers=["ds-user", "lead-user", "mlops-user"],
        rollback_plan_ref="rollback_plan.yaml",
    )

    checks = _policy_map(decision)
    assert checks["verifier_pass"] == "pass"
    assert checks["metric_vs_baseline"] == "pass"
    assert checks["rollback_plan"] == "pass"
    assert checks["feature_alias"] == "pass"
    assert checks["reproducibility"] == "pass"
    assert decision.chain_state == "pending_DS"
    assert decision.approvals[0].status == "pending"
    assert store.get(decision.decision_id) is not None


def test_request_promotion_flags_verifier_failure() -> None:
    gate, _ = _build_gate(
        _run(
            "run-candidate",
            verifier_summary={"statistical": "PASS", "data": "PASS", "policy": "FAIL"},
        )
    )

    decision = gate.evaluate(
        candidate_run_id="run-candidate",
        target_stage="staging",
        approvers=["ds-user", "lead-user", "mlops-user"],
        rollback_plan_ref="rollback_plan.yaml",
    )

    assert _policy_map(decision)["verifier_pass"] == "fail"


def test_request_promotion_flags_metric_regression_against_champion() -> None:
    gate, _ = _build_gate(
        _run("run-candidate", result={"metrics": {"f1_macro": 0.78, "fp_rate": 0.13}})
    )

    decision = gate.evaluate(
        candidate_run_id="run-candidate",
        target_stage="production",
        approvers=["ds-user", "lead-user", "mlops-user"],
        rollback_plan_ref="rollback_plan.yaml",
    )

    assert _policy_map(decision)["metric_vs_baseline"] == "fail"


def test_request_promotion_flags_invalid_rollback_plan() -> None:
    gate, _ = _build_gate(
        _run("run-candidate"),
        rollback_loader=StubRollbackPlanLoader({}, {"bad_plan.yaml": "missing owner"}),
    )

    decision = gate.evaluate(
        candidate_run_id="run-candidate",
        target_stage="canary",
        approvers=["ds-user", "lead-user", "mlops-user"],
        rollback_plan_ref="bad_plan.yaml",
    )

    assert _policy_map(decision)["rollback_plan"] == "fail"


def test_request_promotion_flags_deprecated_feature_usage() -> None:
    candidate = _run(
        "run-candidate",
        feature_refs=[{"feature_id": "f_user_activity_30d", "version": 1}],
    )
    gate, _ = _build_gate(
        candidate,
        feature_store=StubFeatureStore({("f_user_activity_30d", 1): _feature(alias="deprecated")}),
    )

    decision = gate.evaluate(
        candidate_run_id="run-candidate",
        target_stage="production",
        approvers=["ds-user", "lead-user", "mlops-user"],
        rollback_plan_ref="rollback_plan.yaml",
    )

    assert _policy_map(decision)["feature_alias"] == "fail"


def test_request_promotion_flags_diverged_reproducibility() -> None:
    gate, _ = _build_gate(_run("run-candidate", reproducibility_status="diverged"))

    decision = gate.evaluate(
        candidate_run_id="run-candidate",
        target_stage="production",
        approvers=["ds-user", "lead-user", "mlops-user"],
        rollback_plan_ref="rollback_plan.yaml",
    )

    assert _policy_map(decision)["reproducibility"] == "fail"


def test_approve_advances_through_entire_chain() -> None:
    gate, _ = _build_gate(_run("run-candidate"))
    decision = gate.evaluate(
        candidate_run_id="run-candidate",
        target_stage="production",
        approvers=["ds-user", "lead-user", "mlops-user"],
        rollback_plan_ref="rollback_plan.yaml",
    )

    decision = gate.approve(decision.decision_id, approver="ds-user", note="DS approved")
    assert decision.chain_state == "pending_Lead"
    assert decision.approvals[0].status == "approved"

    decision = gate.approve(decision.decision_id, approver="lead-user", note="Lead approved")
    assert decision.chain_state == "pending_MLOps"
    assert decision.approvals[1].status == "approved"

    decision = gate.approve(decision.decision_id, approver="mlops-user", note="MLOps approved")
    assert decision.chain_state == "approved"
    assert decision.approvals[2].status == "approved"
    assert decision.resolved_at is not None


def test_reject_short_circuits_the_chain() -> None:
    gate, _ = _build_gate(_run("run-candidate"))
    decision = gate.evaluate(
        candidate_run_id="run-candidate",
        target_stage="production",
        approvers=["ds-user", "lead-user", "mlops-user"],
        rollback_plan_ref="rollback_plan.yaml",
    )

    decision = gate.reject(decision.decision_id, approver="ds-user", reason="Need more evidence")

    assert decision.chain_state == "rejected"
    assert decision.approvals[0].status == "rejected"
    assert decision.resolved_at is not None

    with pytest.raises(ValueError):
        gate.approve(decision.decision_id, approver="lead-user", note="Too late")


def test_apply_promotes_approved_candidate_to_target_alias_and_retires_previous_alias() -> None:
    candidate_model = _model(
        model_id="m_churn_candidate",
        version=6,
        alias="challenger",
        lineage_run_id="run-candidate",
        artifact={
            "uri": "model://churn/lightgbm/v6",
            "format": "json",
            "size_bytes": 1200,
            "checksum": "candidate",
        },
        description="Candidate churn model.",
    )
    gate, _ = _build_gate(
        _run("run-candidate"),
        model_registry=StubModelRegistry(
            {
                ("m_churn_lightgbm", 5): _model(),
                ("m_churn_candidate", 6): candidate_model,
            }
        ),
    )
    decision = gate.evaluate(
        candidate_run_id="run-candidate",
        target_stage="production",
        approvers=["ds-user", "lead-user", "mlops-user"],
        rollback_plan_ref="rollback_plan.yaml",
    )
    gate.approve(decision.decision_id, approver="ds-user", note="DS approved")
    gate.approve(decision.decision_id, approver="lead-user", note="Lead approved")
    gate.approve(decision.decision_id, approver="mlops-user", note="MLOps approved")

    applied = gate.apply(decision.decision_id)

    assert applied.decision_id == decision.decision_id
    assert applied.applied_alias == "champion"
    assert applied.replaced_model_id == "m_churn_lightgbm"
    assert gate._models.get("m_churn_candidate", 6).alias == "champion"
    assert gate._models.get("m_churn_lightgbm", 5).alias == "retired"


def test_apply_requires_approved_decision() -> None:
    candidate_model = _model(
        model_id="m_churn_candidate",
        version=6,
        alias="challenger",
        lineage_run_id="run-candidate",
        artifact={
            "uri": "model://churn/lightgbm/v6",
            "format": "json",
            "size_bytes": 1200,
            "checksum": "candidate",
        },
        description="Candidate churn model.",
    )
    gate, _ = _build_gate(
        _run("run-candidate"),
        model_registry=StubModelRegistry(
            {
                ("m_churn_lightgbm", 5): _model(),
                ("m_churn_candidate", 6): candidate_model,
            }
        ),
    )
    decision = gate.evaluate(
        candidate_run_id="run-candidate",
        target_stage="production",
        approvers=["ds-user", "lead-user", "mlops-user"],
        rollback_plan_ref="rollback_plan.yaml",
    )

    with pytest.raises(ValueError, match="approved before apply"):
        gate.apply(decision.decision_id)


def test_auto_rollback_restores_previous_champion() -> None:
    gate, store = _build_gate(
        _run("run-candidate"),
        model_registry=StubModelRegistry(
            {
                ("m_churn_lightgbm", 5): _model(
                    model_id="m_churn_lightgbm",
                    version=5,
                    alias="champion",
                    lineage_run_id="run-candidate",
                ),
                ("m_churn_xgboost", 4): _model(
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
                ),
            }
        ),
        rollback_loader=StubRollbackPlanLoader(
            {"rollback_plan.yaml": _rollback_plan("m_churn_xgboost")}
        ),
    )
    decision = gate.evaluate(
        candidate_run_id="run-candidate",
        target_stage="production",
        approvers=["ds-user", "lead-user", "mlops-user"],
        rollback_plan_ref="rollback_plan.yaml",
    )
    approved = decision.model_copy(update={"chain_state": "approved"})
    store.save(approved)

    result = gate.auto_rollback_for_model("m_churn_lightgbm")

    assert result["decision_id"] == decision.decision_id
    assert result["restored_model_id"] == "m_churn_xgboost"
    assert gate._models.get("m_churn_lightgbm", 5).alias == "retired"
    assert gate._models.get("m_churn_xgboost", 4).alias == "champion"
