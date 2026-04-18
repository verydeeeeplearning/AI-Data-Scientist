"""Decision OS promotion-gate use cases."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.application.ports.promotion_gate_support import (
    PromotionDecisionStore,
    RollbackPlanLoader,
)
from ds_agent.application.ports.run_diff_support import (
    ExperimentRunReader,
    MetricDirectionResolver,
)
from ds_agent.domain.entities.experiment import ExperimentRun
from ds_agent.domain.entities.model import Model, ModelAlias
from ds_agent.domain.entities.promotion import (
    ApprovalRole,
    ApprovalStep,
    PolicyCheck,
    PromotionDecision,
    RollbackPlan,
    TargetStage,
)
from ds_agent.domain.interfaces.feature_registry import FeatureRegistryStore
from ds_agent.domain.interfaces.model_registry import ModelRegistryStore


class PromotionApplicationResult(BaseModel):
    """Structured outcome for one applied promotion decision."""

    model_config = ConfigDict(frozen=True)

    decision_id: str = Field(min_length=1)
    candidate_model_id: str = Field(min_length=1)
    candidate_model_version: int = Field(ge=1)
    target_stage: TargetStage
    applied_alias: ModelAlias
    replaced_model_id: str | None = None
    replaced_model_version: int | None = Field(default=None, ge=1)
    applied_at: datetime


class PromotionGate:
    """Evaluate promotion policy and manage approval-chain transitions."""

    _CHAIN_ROLES: tuple[ApprovalRole, ...] = ("DS", "Lead", "MLOps")

    def __init__(
        self,
        experiment_runs: ExperimentRunReader,
        features: FeatureRegistryStore,
        models: ModelRegistryStore,
        decisions: PromotionDecisionStore,
        rollback_plans: RollbackPlanLoader,
        metric_directions: MetricDirectionResolver,
    ) -> None:
        self._experiment_runs = experiment_runs
        self._features = features
        self._models = models
        self._decisions = decisions
        self._rollback_plans = rollback_plans
        self._metric_directions = metric_directions

    def evaluate(
        self,
        candidate_run_id: str,
        target_stage: TargetStage,
        approvers: list[str],
        rollback_plan_ref: str,
    ) -> PromotionDecision:
        candidate = self._load_run(candidate_run_id)
        approvals = self._build_approval_chain(approvers)
        rollback_plan, rollback_check = self._load_rollback_plan(rollback_plan_ref)
        policy_checks = [
            self._verifier_check(candidate),
            self._baseline_metric_check(candidate),
            PolicyCheck(
                name="ab_result",
                status="skipped",
                detail="A/B evidence injection is not wired in this foundation slice.",
            ),
            rollback_check,
            self._feature_alias_check(candidate),
            self._reproducibility_check(candidate),
            PolicyCheck(
                name="uncertainty_range",
                status="skipped",
                detail="Review-artifact uncertainty integration is pending.",
            ),
        ]
        if rollback_plan is not None:
            policy_checks = self._validate_rollback_champion(policy_checks, rollback_plan)
        decision = PromotionDecision(
            decision_id=f"promotion-{uuid.uuid4().hex[:12]}",
            candidate_run_id=candidate.run_id,
            candidate_model_id=self._candidate_model_id(candidate),
            target_stage=target_stage,
            policy_checks=policy_checks,
            approvals=approvals,
            chain_state="pending_DS",
            rollback_plan_ref=rollback_plan_ref,
            created_at=datetime.now(UTC),
        )
        self._decisions.save(decision)
        return decision

    def approve(self, decision_id: str, approver: str, note: str) -> PromotionDecision:
        decision = self._load_decision(decision_id)
        updated = decision.approve(approver=approver, note=note, decided_at=datetime.now(UTC))
        self._decisions.save(updated)
        return updated

    def reject(self, decision_id: str, approver: str, reason: str) -> PromotionDecision:
        decision = self._load_decision(decision_id)
        updated = decision.reject(
            approver=approver,
            reason=reason,
            decided_at=datetime.now(UTC),
        )
        self._decisions.save(updated)
        return updated

    def apply(self, decision_id: str) -> PromotionApplicationResult:
        """Apply one approved promotion decision to the model-registry aliases."""

        decision = self._load_decision(decision_id)
        if decision.chain_state != "approved":
            raise ValueError("Promotion decision must be approved before apply.")

        candidate_model = self._latest_model(decision.candidate_model_id)
        target_alias = self._alias_for_stage(decision.target_stage)
        now = datetime.now(UTC)

        replaced = self._models.get_by_alias(target_alias)
        replaced_effective = (
            replaced
            if replaced is not None and not self._same_model_version(replaced, candidate_model)
            else None
        )
        if replaced_effective is not None:
            self._models.update_alias(
                replaced_effective.model_id,
                replaced_effective.version,
                "retired",
                retired_at=now,
            )

        self._models.update_alias(
            candidate_model.model_id,
            candidate_model.version,
            target_alias,
            promoted_at=now,
            retired_at=None,
        )

        return PromotionApplicationResult(
            decision_id=decision.decision_id,
            candidate_model_id=candidate_model.model_id,
            candidate_model_version=candidate_model.version,
            target_stage=decision.target_stage,
            applied_alias=target_alias,
            replaced_model_id=(None if replaced_effective is None else replaced_effective.model_id),
            replaced_model_version=(
                None if replaced_effective is None else replaced_effective.version
            ),
            applied_at=now,
        )

    def auto_rollback_for_model(self, candidate_model_id: str) -> dict[str, object]:
        """Rollback one deployed model to the rollback-plan champion without approvals."""

        decision = self._latest_approved_decision(candidate_model_id)
        rollback_plan = self._rollback_plans.load(decision.rollback_plan_ref)
        candidate_model = self._latest_model(candidate_model_id)
        previous_champion = self._latest_model(rollback_plan.previous_champion_model_id)
        now = datetime.now(UTC)

        current_champion = self._models.get_by_alias("champion")
        if current_champion is not None and current_champion.model_id != previous_champion.model_id:
            self._models.update_alias(
                current_champion.model_id,
                current_champion.version,
                "retired",
                retired_at=now,
            )
        if candidate_model.alias != "retired":
            self._models.update_alias(
                candidate_model.model_id,
                candidate_model.version,
                "retired",
                retired_at=now,
            )
        self._models.update_alias(
            previous_champion.model_id,
            previous_champion.version,
            "champion",
            promoted_at=now,
        )
        return {
            "decision_id": decision.decision_id,
            "candidate_model_id": candidate_model.model_id,
            "candidate_model_version": candidate_model.version,
            "restored_model_id": previous_champion.model_id,
            "restored_model_version": previous_champion.version,
            "executed_at": now.isoformat(),
            "rollback_plan_ref": decision.rollback_plan_ref,
        }

    def _load_run(self, run_id: str) -> ExperimentRun:
        run = self._experiment_runs.get_run(run_id)
        if run is None:
            raise LookupError(f"Experiment run not found: {run_id}")
        return run

    def _load_decision(self, decision_id: str) -> PromotionDecision:
        decision = self._decisions.get(decision_id)
        if decision is None:
            raise LookupError(f"Promotion decision not found: {decision_id}")
        return decision

    def _latest_approved_decision(self, candidate_model_id: str) -> PromotionDecision:
        decisions = self._decisions.list_for_model(candidate_model_id, limit=20)
        for decision in decisions:
            if decision.chain_state == "approved":
                return decision
        raise LookupError(
            f"No approved promotion decision found for candidate model: {candidate_model_id}"
        )

    def _build_approval_chain(self, approvers: list[str]) -> list[ApprovalStep]:
        if len(approvers) < len(self._CHAIN_ROLES):
            raise ValueError("Promotion requires approvers for DS, Lead, and MLOps.")
        return [
            ApprovalStep(role=role, approver=approver)
            for role, approver in zip(
                self._CHAIN_ROLES,
                approvers[: len(self._CHAIN_ROLES)],
                strict=False,
            )
        ]

    def _load_rollback_plan(
        self,
        rollback_plan_ref: str,
    ) -> tuple[RollbackPlan | None, PolicyCheck]:
        try:
            plan = self._rollback_plans.load(rollback_plan_ref)
        except Exception as exc:
            return (
                None,
                PolicyCheck(
                    name="rollback_plan",
                    status="fail",
                    detail=f"Rollback plan invalid: {exc}",
                ),
            )
        return (
            plan,
            PolicyCheck(
                name="rollback_plan",
                status="pass",
                detail="Rollback plan YAML is present and valid.",
            ),
        )

    def _validate_rollback_champion(
        self,
        checks: list[PolicyCheck],
        rollback_plan: RollbackPlan,
    ) -> list[PolicyCheck]:
        current = self._models.get_by_alias("champion")
        if current is None:
            return checks
        if rollback_plan.previous_champion_model_id == current.model_id:
            return checks
        updated = list(checks)
        for index, check in enumerate(updated):
            if check.name != "rollback_plan":
                continue
            updated[index] = PolicyCheck(
                name="rollback_plan",
                status="fail",
                detail=(
                    "Rollback plan references "
                    f"{rollback_plan.previous_champion_model_id}, expected {current.model_id}."
                ),
            )
            break
        return updated

    @staticmethod
    def _verifier_check(candidate: ExperimentRun) -> PolicyCheck:
        summary = candidate.verifier_summary or {}
        required = ("statistical", "data", "policy")
        failing = [name for name in required if summary.get(name) != "PASS"]
        if failing:
            return PolicyCheck(
                name="verifier_pass",
                status="fail",
                detail="Verifier checks not passing: " + ", ".join(failing),
            )
        return PolicyCheck(
            name="verifier_pass",
            status="pass",
            detail="All verifier categories passed.",
        )

    def _baseline_metric_check(self, candidate: ExperimentRun) -> PolicyCheck:
        champion = self._models.get_by_alias("champion")
        if champion is None:
            return PolicyCheck(
                name="metric_vs_baseline",
                status="skipped",
                detail="No champion model is registered yet.",
            )
        baseline_run = self._experiment_runs.get_run(champion.lineage_run_id)
        if baseline_run is None:
            return PolicyCheck(
                name="metric_vs_baseline",
                status="fail",
                detail=f"Champion lineage run is missing: {champion.lineage_run_id}",
            )
        regressions: list[str] = []
        compared = 0
        for metric_name, candidate_value in candidate.result.metrics.items():
            if metric_name not in baseline_run.result.metrics:
                continue
            compared += 1
            baseline_value = float(baseline_run.result.metrics[metric_name])
            candidate_metric = float(candidate_value)
            direction = self._metric_directions.direction_for(metric_name)
            if direction == "lower_is_better":
                is_regression = candidate_metric > baseline_value
            elif direction == "higher_is_better":
                is_regression = candidate_metric < baseline_value
            else:
                is_regression = False
            if is_regression:
                regressions.append(f"{metric_name}: {baseline_value} -> {candidate_metric}")
        if compared == 0:
            return PolicyCheck(
                name="metric_vs_baseline",
                status="skipped",
                detail="No overlapping metrics with the current champion baseline.",
            )
        if regressions:
            return PolicyCheck(
                name="metric_vs_baseline",
                status="fail",
                detail="Metric regression against champion: " + "; ".join(regressions),
            )
        return PolicyCheck(
            name="metric_vs_baseline",
            status="pass",
            detail=f"Compared {compared} overlapping metrics against the champion baseline.",
        )

    def _feature_alias_check(self, candidate: ExperimentRun) -> PolicyCheck:
        deprecated: list[str] = []
        missing: list[str] = []
        for ref in candidate.feature_refs:
            feature = self._features.get(ref.feature_id, ref.version)
            if feature is None:
                missing.append(f"{ref.feature_id} v{ref.version}")
                continue
            if feature.alias == "deprecated":
                deprecated.append(f"{ref.feature_id} v{ref.version}")
        if deprecated:
            return PolicyCheck(
                name="feature_alias",
                status="fail",
                detail="Deprecated features in candidate: " + ", ".join(deprecated),
            )
        if missing:
            return PolicyCheck(
                name="feature_alias",
                status="warn",
                detail="Feature definitions missing from registry: " + ", ".join(missing),
            )
        return PolicyCheck(
            name="feature_alias",
            status="pass",
            detail="All candidate features are active in the registry.",
        )

    @staticmethod
    def _reproducibility_check(candidate: ExperimentRun) -> PolicyCheck:
        if candidate.reproducibility_status == "diverged":
            return PolicyCheck(
                name="reproducibility",
                status="fail",
                detail="Candidate run diverged from the reproducibility contract.",
            )
        return PolicyCheck(
            name="reproducibility",
            status="pass",
            detail=(f"Reproducibility status is {candidate.reproducibility_status}."),
        )

    def _candidate_model_id(self, candidate: ExperimentRun) -> str:
        models = self._models.list_from_run(candidate.run_id)
        if models:
            latest = max(models, key=lambda item: item.version)
            return latest.model_id
        slug = re.sub(r"[^a-z0-9]+", "_", candidate.experiment_group.casefold()).strip("_")
        family = re.sub(r"[^a-z0-9]+", "_", candidate.method.model_family.casefold()).strip("_")
        parts = [part for part in (slug, family) if part]
        return "m_" + "_".join(parts or ["candidate"])

    def _latest_model(self, model_id: str) -> Model:
        matches = [
            model for model in self._models.list_models(limit=500) if model.model_id == model_id
        ]
        if not matches:
            raise LookupError(f"Model not found in registry: {model_id}")
        return max(matches, key=lambda item: item.version)

    @staticmethod
    def _alias_for_stage(target_stage: TargetStage) -> ModelAlias:
        mapping: dict[TargetStage, ModelAlias] = {
            "staging": "challenger",
            "production": "champion",
            "canary": "canary",
        }
        return mapping[target_stage]

    @staticmethod
    def _same_model_version(left: Model, right: Model) -> bool:
        return (left.model_id, left.version) == (right.model_id, right.version)


class RequestPromotionUseCase:
    """Application-facing wrapper for promotion evaluation."""

    def __init__(self, gate: PromotionGate) -> None:
        self._gate = gate

    def execute(
        self,
        candidate_run_id: str,
        target_stage: TargetStage,
        approvers: list[str],
        rollback_plan_ref: str,
    ) -> PromotionDecision:
        return self._gate.evaluate(
            candidate_run_id=candidate_run_id,
            target_stage=target_stage,
            approvers=approvers,
            rollback_plan_ref=rollback_plan_ref,
        )


class ApprovePromotionUseCase:
    """Application-facing wrapper for approval transitions."""

    def __init__(self, gate: PromotionGate) -> None:
        self._gate = gate

    def execute(self, decision_id: str, approver: str, note: str) -> PromotionDecision:
        return self._gate.approve(decision_id, approver, note)


class RejectPromotionUseCase:
    """Application-facing wrapper for rejection transitions."""

    def __init__(self, gate: PromotionGate) -> None:
        self._gate = gate

    def execute(self, decision_id: str, approver: str, reason: str) -> PromotionDecision:
        return self._gate.reject(decision_id, approver, reason)


class ApplyPromotionUseCase:
    """Application-facing wrapper for applying one approved promotion decision."""

    def __init__(self, gate: PromotionGate) -> None:
        self._gate = gate

    def execute(self, decision_id: str) -> PromotionApplicationResult:
        return self._gate.apply(decision_id)


class AutoRollbackUseCase:
    """Application-facing wrapper for automatic rollback execution."""

    def __init__(self, gate: PromotionGate) -> None:
        self._gate = gate

    def execute(self, candidate_model_id: str) -> dict[str, object]:
        return self._gate.auto_rollback_for_model(candidate_model_id)
