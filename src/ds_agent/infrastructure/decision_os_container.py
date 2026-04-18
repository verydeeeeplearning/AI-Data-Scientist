"""Composition root for Decision OS services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ds_agent.application.ports.post_deploy_support import (
    AutoRetrainExecutor,
    AutoRollbackExecutor,
    DeployMonitorStateStore,
    PostDeployAutomationPolicyResolver,
    PostDeploySnapshotProvider,
)
from ds_agent.application.ports.run_diff_support import MetricDirectionLabel
from ds_agent.application.services.post_deploy_usecases import GetPostDeployStatusUseCase
from ds_agent.application.services.promotion_gate_usecases import (
    ApplyPromotionUseCase,
    ApprovePromotionUseCase,
    AutoRollbackUseCase,
    PromotionGate,
    RejectPromotionUseCase,
    RequestPromotionUseCase,
)
from ds_agent.application.services.review_artifact_usecases import (
    GetReviewArtifactsUseCase,
    RecordReviewArtifactUseCase,
)
from ds_agent.application.services.run_diff_usecases import (
    CompareRunsUseCase,
    HeuristicMetricDirectionResolver,
    RunDiffEngine,
)
from ds_agent.domain.interfaces.feature_registry import FeatureRegistryStore
from ds_agent.domain.interfaces.model_registry import ModelRegistryStore
from ds_agent.infrastructure.importers.yaml_rollback_plan_loader import (
    YamlRollbackPlanLoader,
)
from ds_agent.infrastructure.persistence.deploy_monitor_state_store import (
    SqliteDeployMonitorStateStore,
)
from ds_agent.infrastructure.persistence.feature_registry_store import SqliteFeatureRegistryStore
from ds_agent.infrastructure.persistence.model_registry_store import SqliteModelRegistryStore
from ds_agent.infrastructure.persistence.promotion_decision_store import (
    SqlitePromotionDecisionStore,
)
from ds_agent.infrastructure.semantic_memory_paths import resolve_semantic_db_path
from ds_agent.memory.experiment_log import ExperimentLog
from ds_agent.memory.semantic.application.ports import MetricRepository
from ds_agent.memory.semantic.infrastructure.sqlite_base import SemanticSqliteDatabase
from ds_agent.memory.semantic.infrastructure.sqlite_metric_repo import SqliteMetricRepository
from ds_agent.runtime.post_deploy_monitor import (
    EnvPostDeployAutomationPolicyResolver,
    ExperimentLogAutoRetrainExecutor,
    PostDeployMonitor,
    PromotionGateAutoRollbackExecutor,
    RuntimeEventRecorder,
    WorkspacePostDeploySnapshotProvider,
)


class SemanticMetricDirectionResolver(HeuristicMetricDirectionResolver):
    """Resolve metric direction from semantic memory before using heuristics."""

    def __init__(self, metrics: MetricRepository) -> None:
        self._metrics = metrics

    def direction_for(self, metric_name: str) -> MetricDirectionLabel:
        metric = self._metrics.get(metric_name)
        if metric is not None:
            return metric.direction
        resolved = self._metrics.resolve(metric_name, limit=1)
        if resolved:
            return resolved[0].direction
        return super().direction_for(metric_name)


@dataclass(frozen=True)
class DecisionOsContainer:
    """Wired Decision OS services currently exposed to tools."""

    experiment_log: ExperimentLog
    feature_registry: FeatureRegistryStore
    model_registry: ModelRegistryStore
    promotion_decisions: SqlitePromotionDecisionStore
    deploy_monitor_states: DeployMonitorStateStore
    metric_directions: SemanticMetricDirectionResolver
    compare_runs: CompareRunsUseCase
    request_promotion: RequestPromotionUseCase
    approve_promotion: ApprovePromotionUseCase
    reject_promotion: RejectPromotionUseCase
    apply_promotion: ApplyPromotionUseCase
    auto_rollback: AutoRollbackUseCase
    post_deploy_policy: PostDeployAutomationPolicyResolver
    post_deploy_monitor: PostDeployMonitor
    get_post_deploy_status: GetPostDeployStatusUseCase
    record_review_artifact: RecordReviewArtifactUseCase
    get_review_artifacts: GetReviewArtifactsUseCase


def build_decision_os_container(
    workspace_dir: str | None = None,
    *,
    experiment_log: ExperimentLog | None = None,
    feature_store: FeatureRegistryStore | None = None,
    model_store: ModelRegistryStore | None = None,
    promotion_store: SqlitePromotionDecisionStore | None = None,
    deploy_monitor_store: DeployMonitorStateStore | None = None,
    metric_repo: MetricRepository | None = None,
    snapshot_provider: PostDeploySnapshotProvider | None = None,
    runtime_event_log: RuntimeEventRecorder | None = None,
    post_deploy_policy: PostDeployAutomationPolicyResolver | None = None,
    auto_retrain_executor: AutoRetrainExecutor | None = None,
    auto_rollback_executor: AutoRollbackExecutor | None = None,
) -> DecisionOsContainer:
    """Build the Decision OS container for one workspace."""

    resolved_log = experiment_log or ExperimentLog(_default_experiment_log_dir(workspace_dir))
    resolved_feature_store = feature_store or SqliteFeatureRegistryStore.for_workspace(
        workspace_dir
    )
    resolved_model_store = model_store or SqliteModelRegistryStore.for_workspace(workspace_dir)
    resolved_promotion_store = promotion_store or SqlitePromotionDecisionStore.for_workspace(
        workspace_dir
    )
    resolved_deploy_monitor_store = deploy_monitor_store or (
        SqliteDeployMonitorStateStore.for_workspace(workspace_dir)
    )
    resolved_metric_repo = metric_repo or SqliteMetricRepository(
        SemanticSqliteDatabase(_default_semantic_db_path(workspace_dir))
    )
    resolved_snapshot_provider = snapshot_provider or WorkspacePostDeploySnapshotProvider(
        workspace_dir
    )
    if runtime_event_log is None:
        from ds_agent.runtime.runtime_event_log import RuntimeEventLog

        resolved_runtime_event_log: RuntimeEventRecorder = RuntimeEventLog(
            workspace_dir=workspace_dir
        )
    else:
        resolved_runtime_event_log = runtime_event_log
    resolved_post_deploy_policy = cast(
        PostDeployAutomationPolicyResolver,
        post_deploy_policy or EnvPostDeployAutomationPolicyResolver(),
    )
    resolver = SemanticMetricDirectionResolver(resolved_metric_repo)
    engine = RunDiffEngine(resolved_log, resolver)
    promotion_gate = PromotionGate(
        resolved_log,
        resolved_feature_store,
        resolved_model_store,
        resolved_promotion_store,
        YamlRollbackPlanLoader(workspace_dir),
        resolver,
    )
    auto_rollback_use_case = AutoRollbackUseCase(promotion_gate)
    post_deploy_monitor = PostDeployMonitor(
        experiment_runs=resolved_log,
        models=resolved_model_store,
        state_store=resolved_deploy_monitor_store,
        snapshot_provider=resolved_snapshot_provider,
        event_log=resolved_runtime_event_log,
        metric_directions=resolver,
        trigger_policy=resolved_post_deploy_policy,
        auto_retrain_executor=auto_retrain_executor
        or ExperimentLogAutoRetrainExecutor(resolved_log),
        auto_rollback_executor=auto_rollback_executor
        or PromotionGateAutoRollbackExecutor(auto_rollback_use_case.execute),
    )
    return DecisionOsContainer(
        experiment_log=resolved_log,
        feature_registry=resolved_feature_store,
        model_registry=resolved_model_store,
        promotion_decisions=resolved_promotion_store,
        deploy_monitor_states=resolved_deploy_monitor_store,
        metric_directions=resolver,
        compare_runs=CompareRunsUseCase(engine),
        request_promotion=RequestPromotionUseCase(promotion_gate),
        approve_promotion=ApprovePromotionUseCase(promotion_gate),
        reject_promotion=RejectPromotionUseCase(promotion_gate),
        apply_promotion=ApplyPromotionUseCase(promotion_gate),
        auto_rollback=auto_rollback_use_case,
        post_deploy_policy=resolved_post_deploy_policy,
        post_deploy_monitor=post_deploy_monitor,
        get_post_deploy_status=GetPostDeployStatusUseCase(resolved_deploy_monitor_store),
        record_review_artifact=RecordReviewArtifactUseCase(resolved_log),
        get_review_artifacts=GetReviewArtifactsUseCase(resolved_log),
    )


def _default_experiment_log_dir(workspace_dir: str | None) -> str:
    if workspace_dir is not None:
        return str(Path(workspace_dir) / "data" / "memory" / "experiment_log")
    return "data/memory/experiment_log"


def _default_semantic_db_path(workspace_dir: str | None) -> str:
    return str(resolve_semantic_db_path(workspace_dir))
