"""Runtime adapter for Decision OS post-deploy monitoring."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Protocol

from ds_agent.application.ports.post_deploy_support import (
    AutoRetrainExecutor,
    AutoRollbackExecutor,
    DeployMonitorStateStore,
    PostDeployAutomationPolicyResolver,
    PostDeploySnapshotProvider,
)
from ds_agent.application.ports.run_diff_support import (
    ExperimentRunReader,
    MetricDirectionResolver,
)
from ds_agent.application.services.drift_analyzer import DriftAnalyzer
from ds_agent.application.services.remediation_service import RemediationService
from ds_agent.domain.entities.experiment import ExperimentRun, Hypothesis, RunResult
from ds_agent.domain.entities.model import Model
from ds_agent.domain.entities.post_deploy import (
    DriftMetricObservation,
    DriftSummary,
    MetricChangeObservation,
    PostDeployMonitorState,
    PostDeploySnapshot,
    RemediationSummary,
    ServiceLevelSummary,
)
from ds_agent.domain.interfaces.model_registry import ModelRegistryStore
from ds_agent.memory.experiment_log import ExperimentLog


class RuntimeEventRecorder(Protocol):
    """Minimal runtime-event writer used by the post-deploy monitor."""

    def record(
        self,
        *,
        category: str,
        kind: str,
        severity: str,
        message: str,
        session_id: str | None = None,
        run_id: str | None = None,
        surface: str = "daemon",
        source: str = "runtime",
        metadata: dict[str, object] | None = None,
        created_at: float | None = None,
    ) -> object: ...


class WorkspacePostDeploySnapshotProvider:
    """Load post-deploy snapshots from workspace-local JSON files."""

    def __init__(self, workspace_dir: str | None = None) -> None:
        if workspace_dir is not None:
            self._dir = Path(workspace_dir) / "data" / "monitoring" / "post_deploy"
        else:
            self._dir = Path("data") / "monitoring" / "post_deploy"

    def load(self, model_id: str, model_version: int) -> PostDeploySnapshot | None:
        candidates = [
            self._dir / f"{model_id}-v{model_version}.json",
            self._dir / f"{model_id}.json",
        ]
        for path in candidates:
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"Invalid post-deploy snapshot payload: {path}")
            return PostDeploySnapshot.model_validate(payload)
        return None


class StaticPostDeployAutomationPolicyResolver:
    """Resolve one fixed trigger mode and cron schedule for all monitored models."""

    def __init__(
        self,
        *,
        trigger_mode: str = "manual_only",
        cron: str = "*/15 * * * *",
    ) -> None:
        self._trigger_mode = _normalize_trigger_mode(trigger_mode)
        self._cron = cron.strip() or "*/15 * * * *"

    def mode_for(self, model_id: str, alias: str) -> str:
        del model_id, alias
        return self._trigger_mode

    def schedule_cron(self) -> str:
        return self._cron


class EnvPostDeployAutomationPolicyResolver(StaticPostDeployAutomationPolicyResolver):
    """Resolve trigger mode and cron schedule from process environment."""

    def __init__(self) -> None:
        super().__init__(
            trigger_mode=os.getenv("DS_AGENT_DECISION_OS_TRIGGER_MODE", "manual_only"),
            cron=os.getenv("DS_AGENT_DECISION_OS_MONITOR_CRON", "*/15 * * * *"),
        )


class ExperimentLogAutoRetrainExecutor:
    """Create one candidate experiment run when auto-retrain is enabled."""

    def __init__(self, experiment_log: ExperimentLog) -> None:
        self._experiment_log = experiment_log

    def execute(
        self,
        model: Model,
        baseline_run: ExperimentRun,
        state: PostDeployMonitorState,
    ) -> dict[str, object]:
        runs = self._experiment_log.list_runs(
            experiment_group=baseline_run.experiment_group,
            limit=10_000,
        )
        sequence = max((run.sequence for run in runs), default=baseline_run.sequence) + 1
        run_id = self._next_run_id(baseline_run.experiment_group, sequence)
        candidate = ExperimentRun(
            run_id=run_id,
            experiment_group=baseline_run.experiment_group,
            sequence=sequence,
            hypothesis=Hypothesis(
                statement=f"Auto-retrain candidate for {model.model_id}",
                rationale=(f"Triggered by post-deploy monitor: {state.remediation.rationale}"),
                expected_effect=baseline_run.hypothesis.expected_effect,
            ),
            method=baseline_run.method,
            feature_refs=baseline_run.feature_refs,
            data_snapshot_uri=state.trigger_payload.get(
                "snapshot_uri",
                baseline_run.data_snapshot_uri,
            ),
            result=RunResult(metrics={}),
            verifier_report_id=None,
            verifier_summary=None,
            verifier_findings=[],
            created_at=state.observed_at,
            owner="decision-os",
            status="running",
            parent_run_id=baseline_run.run_id,
            promotion_state="candidate",
            reproducibility_status="unknown",
        )
        self._experiment_log.record_extended(candidate)
        return {
            "created_run_id": candidate.run_id,
            "experiment_group": candidate.experiment_group,
            "sequence": candidate.sequence,
            "parent_run_id": baseline_run.run_id,
        }

    def _next_run_id(self, experiment_group: str, sequence: int) -> str:
        while True:
            run_id = f"{experiment_group}_auto_retrain_{sequence:03d}"
            if self._experiment_log.get_run(run_id) is None:
                return run_id
            sequence += 1


class PromotionGateAutoRollbackExecutor:
    """Execute automatic rollback via the Decision OS promotion gate."""

    def __init__(self, execute_rollback) -> None:
        self._execute_rollback = execute_rollback

    def execute(
        self,
        model: Model,
        state: PostDeployMonitorState,
    ) -> dict[str, object]:
        del state
        return self._execute_rollback(model.model_id)


class PostDeployMonitor:
    """Monitor deployed Decision OS models and persist sweep state."""

    _ACTIVE_ALIASES = frozenset({"champion", "canary"})

    def __init__(
        self,
        *,
        experiment_runs: ExperimentRunReader,
        models: ModelRegistryStore,
        state_store: DeployMonitorStateStore,
        snapshot_provider: PostDeploySnapshotProvider,
        event_log: RuntimeEventRecorder,
        metric_directions: MetricDirectionResolver,
        trigger_policy: PostDeployAutomationPolicyResolver | None = None,
        auto_retrain_executor: AutoRetrainExecutor | None = None,
        auto_rollback_executor: AutoRollbackExecutor | None = None,
    ) -> None:
        self._experiment_runs = experiment_runs
        self._models = models
        self._state_store = state_store
        self._snapshot_provider = snapshot_provider
        self._event_log = event_log
        self._metric_directions = metric_directions
        self._trigger_policy = trigger_policy or EnvPostDeployAutomationPolicyResolver()
        self._auto_retrain_executor = auto_retrain_executor
        self._auto_rollback_executor = auto_rollback_executor
        self._drift = DriftAnalyzer(warning_threshold=0.2, danger_threshold=0.3)
        self._remediation = RemediationService()

    def periodic_sweep(self, *, window: str = "24h") -> list[PostDeployMonitorState]:
        """Sweep all active models that have monitoring snapshots available."""

        states: list[PostDeployMonitorState] = []
        for model in self._models.list_models(limit=200):
            if model.alias not in self._ACTIVE_ALIASES:
                continue
            state = self._sweep_model(model, window=window)
            if state is not None:
                states.append(state)
        return states

    def _sweep_model(self, model: Model, *, window: str) -> PostDeployMonitorState | None:
        snapshot = self._snapshot_provider.load(model.model_id, model.version)
        if snapshot is None:
            return None
        baseline = self._experiment_runs.get_run(model.lineage_run_id)
        if baseline is None:
            self._event_log.record(
                category="deployment",
                kind="post_deploy_skipped",
                severity="warning",
                message=f"Skipped post-deploy sweep for {model.model_id}: baseline run missing.",
                metadata={
                    "model_id": model.model_id,
                    "model_version": model.version,
                    "lineage_run_id": model.lineage_run_id,
                },
            )
            return None

        feature_names = [ref.feature_id for ref in model.serving.feature_refs] or None
        drift_report = self._drift.analyze(
            snapshot.reference_path,
            snapshot.current_path,
            features=feature_names,
        )
        drift_summary = DriftSummary(
            overall_status=drift_report.overall_status,
            max_psi=_max_metric(drift_report, "PSI"),
            max_ks=_max_metric(drift_report, "KS"),
            top_drifting_features=drift_report.top_drifting_features,
            metrics=[
                DriftMetricObservation(
                    feature_name=metric.feature_name,
                    metric_type=metric.metric_type,
                    value=metric.value,
                    threshold=metric.threshold,
                    level=metric.level,
                )
                for metric in drift_report.metrics
            ],
        )

        metric_changes, worst_performance_delta = self._metric_changes(
            baseline.result.metrics,
            snapshot.current_metrics,
        )
        service_level = self._service_level(model, snapshot)
        remediation = self._remediation.decide(
            drift_score=drift_summary.max_psi or 0.0,
            performance_delta=worst_performance_delta,
        )
        remediation_summary = RemediationSummary(
            decision=remediation.decision,
            severity=remediation.severity,
            rationale=remediation.rationale,
            should_alert=remediation.should_alert,
            recommended_steps=remediation.recommended_steps,
        )
        overall_status = self._overall_status(
            drift_status=drift_summary.overall_status,
            metric_changes=metric_changes,
            service_level=service_level,
            remediation=remediation_summary,
        )
        alerts = self._alerts(
            drift=drift_summary,
            metrics=metric_changes,
            service_level=service_level,
            remediation=remediation_summary,
        )
        state = PostDeployMonitorState(
            state_id=f"deploy-{uuid.uuid4().hex[:12]}",
            model_id=model.model_id,
            model_version=model.version,
            alias=model.alias,
            window=window,
            observed_at=snapshot.observed_at,
            drift=drift_summary,
            metrics=metric_changes,
            service_level=service_level,
            remediation=remediation_summary,
            overall_status=overall_status,
            alerts=alerts,
            trigger_mode=self._trigger_policy.mode_for(model.model_id, model.alias),
            trigger_payload={
                **self._remediation.build_trigger_payload(remediation, model_id=model.model_id),
                "snapshot_uri": snapshot.current_path,
                "executed": False,
            },
        )
        state = self._apply_trigger_execution(
            model=model,
            baseline=baseline,
            state=state,
        )
        self._state_store.save(state)
        if alerts:
            self._event_log.record(
                category="deployment",
                kind="post_deploy_alert",
                severity="critical" if overall_status == "alert" else "warning",
                message=f"Post-deploy alert for {model.model_id}: {alerts[0]}",
                metadata=state.model_dump(mode="json"),
            )
        return state

    def _apply_trigger_execution(
        self,
        *,
        model: Model,
        baseline: ExperimentRun,
        state: PostDeployMonitorState,
    ) -> PostDeployMonitorState:
        action = state.remediation.decision
        try:
            if (
                action == "retrain"
                and state.trigger_mode in {"auto_retrain", "auto_rollback"}
                and self._auto_retrain_executor is not None
            ):
                execution = self._auto_retrain_executor.execute(model, baseline, state)
                payload = {
                    **state.trigger_payload,
                    "executed": True,
                    "execution": execution,
                }
                self._event_log.record(
                    category="deployment",
                    kind="post_deploy_auto_retrain_requested",
                    severity="warning",
                    message=f"Automatic retrain requested for {model.model_id}.",
                    metadata={**payload, "model_id": model.model_id},
                )
                return state.model_copy(update={"trigger_payload": payload})
            if (
                action == "rollback"
                and state.trigger_mode == "auto_rollback"
                and self._auto_rollback_executor is not None
            ):
                execution = self._auto_rollback_executor.execute(model, state)
                payload = {
                    **state.trigger_payload,
                    "executed": True,
                    "execution": execution,
                }
                self._event_log.record(
                    category="deployment",
                    kind="post_deploy_auto_rollback_executed",
                    severity="critical",
                    message=f"Automatic rollback executed for {model.model_id}.",
                    metadata={**payload, "model_id": model.model_id},
                )
                return state.model_copy(update={"trigger_payload": payload})
        except Exception as exc:
            payload = {
                **state.trigger_payload,
                "executed": False,
                "execution_error": str(exc),
            }
            alerts = list(state.alerts)
            alerts.append(f"Automatic {action} execution failed: {exc}")
            self._event_log.record(
                category="deployment",
                kind="post_deploy_auto_action_failed",
                severity="error",
                message=f"Automatic {action} failed for {model.model_id}: {exc}",
                metadata={**payload, "model_id": model.model_id},
            )
            return state.model_copy(
                update={
                    "trigger_payload": payload,
                    "alerts": alerts,
                    "overall_status": "alert",
                }
            )
        return state

    def _metric_changes(
        self,
        baseline_metrics: dict[str, float],
        current_metrics: dict[str, float],
    ) -> tuple[list[MetricChangeObservation], float]:
        changes: list[MetricChangeObservation] = []
        worst = 0.0
        for metric_name in sorted(set(baseline_metrics) & set(current_metrics)):
            baseline_value = float(baseline_metrics[metric_name])
            current_value = float(current_metrics[metric_name])
            delta = current_value - baseline_value
            direction_label = self._metric_directions.direction_for(metric_name)
            if direction_label == "lower_is_better":
                effectiveness = baseline_value - current_value
            elif direction_label == "higher_is_better":
                effectiveness = current_value - baseline_value
            else:
                effectiveness = 0.0
            worst = min(worst, effectiveness)
            if effectiveness > 0:
                direction = "better"
                status = "ok"
            elif effectiveness < 0:
                direction = "worse"
                status = "alert" if abs(effectiveness) >= 0.05 else "warning"
            else:
                direction = "neutral"
                status = "ok"
            changes.append(
                MetricChangeObservation(
                    metric=metric_name,
                    baseline_value=baseline_value,
                    current_value=current_value,
                    delta=delta,
                    direction=direction,
                    status=status,
                )
            )
        return changes, worst

    @staticmethod
    def _service_level(model: Model, snapshot: PostDeploySnapshot) -> ServiceLevelSummary:
        status = "skipped"
        latency_budget = model.serving.latency_budget_ms
        throughput_budget = model.serving.throughput_budget_qps
        if snapshot.latency_p95_ms is not None and latency_budget is not None:
            if snapshot.latency_p95_ms > latency_budget * 1.2:
                status = "alert"
            elif snapshot.latency_p95_ms > latency_budget:
                status = "warning"
            else:
                status = "ok"
        if snapshot.qps is not None and throughput_budget is not None:
            qps_status = "ok"
            if snapshot.qps < throughput_budget * 0.8:
                qps_status = "alert"
            elif snapshot.qps < throughput_budget:
                qps_status = "warning"
            status = _max_status(status, qps_status)
        return ServiceLevelSummary(
            latency_p95_ms=snapshot.latency_p95_ms,
            latency_budget_ms=latency_budget,
            qps=snapshot.qps,
            throughput_budget_qps=throughput_budget,
            status=status,
        )

    @staticmethod
    def _overall_status(
        *,
        drift_status: str,
        metric_changes: list[MetricChangeObservation],
        service_level: ServiceLevelSummary,
        remediation: RemediationSummary,
    ) -> str:
        status = "ok"
        if drift_status == "warning":
            status = "warning"
        if drift_status == "danger":
            status = "alert"
        for metric in metric_changes:
            status = _max_status(status, metric.status)
        status = _max_status(status, service_level.status)
        if remediation.should_alert:
            status = "alert"
        return status

    @staticmethod
    def _alerts(
        *,
        drift: DriftSummary,
        metrics: list[MetricChangeObservation],
        service_level: ServiceLevelSummary,
        remediation: RemediationSummary,
    ) -> list[str]:
        alerts: list[str] = []
        if drift.max_psi is not None:
            if drift.max_psi > 0.3:
                alerts.append(f"Feature drift alert: PSI={drift.max_psi:.3f}")
            elif drift.max_psi > 0.2:
                alerts.append(f"Feature drift warning: PSI={drift.max_psi:.3f}")
        for metric in metrics:
            if metric.status in {"warning", "alert"}:
                alerts.append(
                    f"Metric {metric.metric} moved from {metric.baseline_value:.4f} "
                    f"to {metric.current_value:.4f}"
                )
        if service_level.status in {"warning", "alert"}:
            alerts.append(
                "Serving SLO deviation detected "
                f"(latency_p95_ms={service_level.latency_p95_ms}, qps={service_level.qps})."
            )
        if remediation.should_alert:
            alerts.append(remediation.rationale)
        return alerts


def _max_metric(report, metric_type: str) -> float | None:
    values = [metric.value for metric in report.metrics if metric.metric_type == metric_type]
    return max(values) if values else None


def _max_status(left: str, right: str) -> str:
    severity = {"skipped": 0, "ok": 1, "warning": 2, "alert": 3}
    return left if severity.get(left, 0) >= severity.get(right, 0) else right


def _normalize_trigger_mode(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"manual_only", "auto_retrain", "auto_rollback"}:
        return "manual_only"
    return normalized
