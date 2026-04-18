"""Shared agent factory — single source of truth for DSAgent wiring.

GAP-05 fix: all entrypoints (WebSocket, CLI, Telegram) use this factory
so hooks, skills, memory, and prompt builder are consistently wired.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import structlog

from ds_agent.agent.backtrack_hook import BacktrackTriggerHook
from ds_agent.agent.builtin_hooks import (
    AuditLogHook,
    BudgetGuardHook,
    ExecPlanSaveHook,
    ExperimentTrackerHook,
    OrgPolicyHook,
    PermissionHook,
    ProblemTypeRouterHook,
    ProcessMetricsHook,
    ReviewArtifactCaptureHook,
    SessionInitHook,
)
from ds_agent.agent.core import DSAgent
from ds_agent.agent.ds_workflow_hooks import (
    BaselineGuardHook,
    DriftDetectionHook,
    ExperimentDesignHook,
    LeakageDetectionHook,
    ModelSanityCheckHook,
    OverfittingDetectorHook,
    ProfileResultsHook,
    StageQualityHook,
    WorkflowTrackerHook,
)
from ds_agent.agent.governance_hooks import (
    LineageCaptureHook,
    PIIRedactionHook,
    PolicyApprovalHook,
)
from ds_agent.agent.hooks import HookRegistry
from ds_agent.agent.prompt_builder import PromptBuilder
from ds_agent.agent.query_cost_guard_hook import QueryCostGuardHook
from ds_agent.agent.reporting_hooks import ClaimTraceabilityHook
from ds_agent.agent.self_debug_hook import SelfDebugHook
from ds_agent.agent.semantic_hooks import (
    SemanticReadGuardHook,
    SemanticTrustHook,
    SemanticWritebackHook,
)
from ds_agent.agent.temporal_join_guard_hook import TemporalJoinGuardHook
from ds_agent.domain.interfaces.certification import CertificationStore
from ds_agent.domain.interfaces.llm_provider import AgentCallbacks, LLMProvider
from ds_agent.domain.interfaces.session_state import (
    CheckpointStore,
    GoalStore,
    TranscriptStore,
    WorkingMemoryStore,
)
from ds_agent.domain.interfaces.task_contract import TaskContractStore
from ds_agent.domain.value_objects.authority_mode import AuthorityMode
from ds_agent.domain.value_objects.budget import BudgetPolicy
from ds_agent.domain.value_objects.connector import ConnectorConfig
from ds_agent.infrastructure.persistence.certification_store import SqliteCertificationStore
from ds_agent.infrastructure.task_contract_container import build_task_contract_container
from ds_agent.infrastructure.verifier_container import build_verifier_container
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.goal_store import JsonGoalStore
from ds_agent.runtime.memory_query_service import MemoryQueryService
from ds_agent.runtime.policy_store import JsonPolicyStore
from ds_agent.runtime.transcript_store import get_runtime_storage_root
from ds_agent.runtime.working_memory import JsonWorkingMemoryStore
from ds_agent.skills.domain_pack_loader import DomainPackLoader
from ds_agent.skills.hub import SkillHub
from ds_agent.skills.mission_pack_loader import MissionPackLoader
from ds_agent.tools.registry import ToolRegistry

logger = structlog.get_logger()

# Builtin skill directory (relative to this file)
_BUILTIN_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills" / "builtin"
_SHARED_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills" / "shared"
_CUSTOM_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills" / "custom"

# Default skill names injected into every session prompt
_DEFAULT_SKILL_NAMES = [
    "scoping",
    "data-profiling",
    "eda",
    "feature-engineering",
    "modeling",
    "evaluation",
    "reporting",
]


def _publish_sandbox_policy(sandbox_config: Any | None, workspace_dir: str | None) -> None:
    """Convert SandboxConfig (pydantic) into a SandboxPolicy and publish it.

    Called from ``create_agent`` before any tool instantiates a sandbox.
    Silently no-ops when no workspace is configured — the sandbox falls back
    to its built-in defaults in that case.
    """
    from ds_agent.domain.entities.sandbox import SandboxPolicy
    from ds_agent.tools.sandbox_context import set_active_sandbox_config

    if workspace_dir is None:
        set_active_sandbox_config(None)
        return

    ws = Path(workspace_dir).expanduser().resolve()
    if sandbox_config is None:
        set_active_sandbox_config(SandboxPolicy(workspace_dir=ws))
        return

    data_dirs = tuple(
        Path(d).expanduser().resolve() for d in getattr(sandbox_config, "data_dirs", ()) or ()
    )
    approved_hosts = tuple(getattr(sandbox_config, "approved_hosts", ()) or ())
    set_active_sandbox_config(
        SandboxPolicy(
            workspace_dir=ws,
            data_dirs=data_dirs,
            approved_hosts=approved_hosts,
            timeout_seconds=int(getattr(sandbox_config, "timeout_seconds", 120)),
            max_memory_mb=int(getattr(sandbox_config, "max_memory_mb", 2048)),
            block_subprocess=bool(getattr(sandbox_config, "block_subprocess", True)),
        )
    )


def import_all_tools() -> None:
    """Import tool modules to trigger self-registration."""
    import importlib

    for module_name in [
        "ds_agent.tools.ab_test_tools",
        "ds_agent.tools.code_execution",
        "ds_agent.tools.data_loader",
        "ds_agent.tools.data_profiler",
        "ds_agent.tools.deployment",
        "ds_agent.tools.distributed_tools",
        "ds_agent.tools.drift_tools",
        "ds_agent.tools.eda",
        "ds_agent.tools.evaluation",
        "ds_agent.tools.feature_eng",
        "ds_agent.tools.file_ops",
        "ds_agent.tools.memory_tools",
        "ds_agent.tools.modeling",
        "ds_agent.tools.reporting",
        "ds_agent.tools.artifact_tools",
        "ds_agent.tools.governance_tools",
        "ds_agent.tools.integration_tools",
        "ds_agent.tools.lookup_term",
        "ds_agent.tools.load_semantic_pack",
        "ds_agent.tools.schema_tools",
        "ds_agent.tools.describe_table_trust",
        "ds_agent.tools.decision_os_tools",
        "ds_agent.tools.feature_registry_tools",
        "ds_agent.tools.semantic_query",
        "ds_agent.tools.skill_tools",
        "ds_agent.tools.sql_tools",
        "ds_agent.tools.standing_order_tools",
        "ds_agent.tools.task_contract_tools",
        "ds_agent.tools.verifier_tool",
        "ds_agent.tools.user_interaction",
        "ds_agent.tools.web_search",
    ]:
        importlib.import_module(module_name)


def build_hook_registry(
    max_cost_usd: float = 10.0,
    *,
    workspace_dir: str | None = None,
    org_policy_supplier: Any | None = None,
    task_contract_store: TaskContractStore | None = None,
    mission_loader: MissionPackLoader | None = None,
    certification_store: CertificationStore | None = None,
    policy_store: JsonPolicyStore | None = None,
) -> HookRegistry:
    """Create and populate a HookRegistry with all hooks."""
    registry = HookRegistry()
    audit_log_path = get_runtime_storage_root(workspace_dir) / "audit_log.jsonl"
    for hook in [
        AuditLogHook(log_path=audit_log_path),
        SessionInitHook(),
        ProcessMetricsHook(),
        ProblemTypeRouterHook(),
        WorkflowTrackerHook(),
        PermissionHook(
            task_contract_store=task_contract_store,
            mission_loader=mission_loader,
            certification_store=certification_store,
            policy_store=policy_store,
        ),
        OrgPolicyHook(org_policy_supplier=org_policy_supplier),
        PolicyApprovalHook(),
        PIIRedactionHook(),
        SemanticReadGuardHook(),
        SemanticTrustHook(),
        SemanticWritebackHook(),
        QueryCostGuardHook(),
        BudgetGuardHook(max_cost_usd=max_cost_usd),
        BaselineGuardHook(),
        TemporalJoinGuardHook(),
        LeakageDetectionHook(),
        SelfDebugHook(),
        OverfittingDetectorHook(),
        BacktrackTriggerHook(),
        ModelSanityCheckHook(),
        ExperimentDesignHook(),
        StageQualityHook(),
        ProfileResultsHook(),
        ExperimentTrackerHook(),
        LineageCaptureHook(),
        ClaimTraceabilityHook(),
        DriftDetectionHook(),
        ExecPlanSaveHook(),
        ReviewArtifactCaptureHook(workspace_dir=workspace_dir),
    ]:
        registry.register(hook)
    return registry


def build_prompt_builder(
    model_name: str | None = None,
    workspace_dir: str | None = None,
    project_id: str | None = None,
    session_id: str | None = None,
    mode: str | None = None,
    use_case_hint: str | None = None,
    use_case_context: str | None = None,
    skill_hub: SkillHub | None = None,
    domain_pack: str | list[str] | None = None,
    goal_store: GoalStore | None = None,
    working_memory_store: WorkingMemoryStore | None = None,
    task_contract_store: TaskContractStore | None = None,
    language: str | None = None,
    authority_mode: AuthorityMode | str | None = None,
    mission_loader: MissionPackLoader | None = None,
) -> PromptBuilder:
    """Build a fully-wired PromptBuilder with skills, memory, and context."""
    skill_names = list(_DEFAULT_SKILL_NAMES)
    packs = _normalize_domain_packs(domain_pack)
    if packs:
        skill_names.extend(DomainPackLoader().get_default_skill_names(packs))
    effective_skill_hub = skill_hub
    if effective_skill_hub is None:
        if packs:
            loader = DomainPackLoader()
            effective_skill_hub = loader.build_skill_hub(packs)
        else:
            effective_skill_hub = SkillHub.from_directories(
                [_BUILTIN_SKILLS_DIR, _SHARED_SKILLS_DIR, _CUSTOM_SKILLS_DIR]
            )

    # Build memory hints
    memory_hints = _build_memory_hints(workspace_dir or ".")

    # Build project context (GAP-04 fix)
    project_context = _build_project_context(workspace_dir, project_id)

    return PromptBuilder(
        skill_hub=effective_skill_hub,
        skill_names=skill_names,  # GAP-04/5.2 fix
        tool_registry=ToolRegistry,
        memory_hints=memory_hints,
        project_context=project_context,
        use_case_hint=use_case_hint,
        use_case_context=use_case_context,
        model_name=model_name,
        workspace_dir=workspace_dir,
        session_id=session_id,
        goal_store=goal_store,
        working_memory_store=working_memory_store,
        task_contract_store=task_contract_store,
        language=language,
        legacy_agent_mode=mode,
        authority_mode=authority_mode,
        mission_loader=mission_loader or MissionPackLoader(),
    )


def create_agent(
    *,
    provider: LLMProvider,
    callbacks: AgentCallbacks,
    max_iterations: int = 100,
    max_cost_usd: float = 10.0,
    mode: str = "auto",
    authority_mode: AuthorityMode | str | None = None,
    model_name: str | None = None,
    workspace_dir: str | None = None,
    project_id: str | None = None,
    session_id: str | None = None,
    use_case_hint: str | None = None,
    use_case_context: str | None = None,
    domain_pack: str | list[str] | None = None,
    api_keys: dict[str, str] | None = None,
    transcript_store: TranscriptStore | None = None,
    checkpoint_store: CheckpointStore | None = None,
    goal_store: GoalStore | None = None,
    working_memory_store: WorkingMemoryStore | None = None,
    task_contract_store: TaskContractStore | None = None,
    approval_store: object | None = None,
    connector_configs: Mapping[str, ConnectorConfig] | None = None,
    skill_hub: SkillHub | None = None,
    org_policy_supplier: Any | None = None,
    sandbox_config: Any | None = None,
    language: str | None = None,
) -> DSAgent:
    """Create a fully-wired DSAgent — single source of truth for all entrypoints.

    ``sandbox_config`` accepts a ``ds_agent.config.schema.SandboxConfig`` (or
    ``None`` for defaults). When provided, sandboxed tool executions use the
    configured timeouts, approved hosts, and read-only data directories.
    """
    import_all_tools()

    # 2.1/3.4 fix: Set active workspace so file_ops and sandbox tools enforce boundaries
    if workspace_dir:
        from ds_agent.tools.path_utils import set_active_workspace

        set_active_workspace(Path(workspace_dir).expanduser().resolve())

    # P0-01 Phase 4: publish sandbox policy for create_sandbox() to read
    _publish_sandbox_policy(sandbox_config, workspace_dir)

    if connector_configs:
        _initialize_warehouse_adapters(connector_configs)

    mission_loader = MissionPackLoader()

    # Build skill hub once — shared by prompt builder and skill_tools (4.5 fix)
    packs = _normalize_domain_packs(domain_pack)
    if skill_hub is not None:
        shared_skill_hub = skill_hub
    elif packs:
        shared_skill_hub = DomainPackLoader().build_skill_hub(packs)
    else:
        shared_skill_hub = SkillHub.from_directories(
            [_BUILTIN_SKILLS_DIR, _SHARED_SKILLS_DIR, _CUSTOM_SKILLS_DIR]
        )
    from ds_agent.tools.skill_tools import set_skill_hub

    set_skill_hub(shared_skill_hub)
    from ds_agent.application.services.scheduler_service import (
        SchedulerService,
        set_scheduler_service,
    )
    from ds_agent.infrastructure.cron_runner import CronRunner
    from ds_agent.tools.memory_tools import set_memory_query_service, set_unified_memory_store

    set_memory_query_service(MemoryQueryService.from_workspace(workspace_dir))
    policy_store = JsonPolicyStore(workspace_dir)
    set_scheduler_service(
        SchedulerService(
            store=policy_store,
            cron_runner=CronRunner(),
        )
    )

    # Composition root: wire the lineage service onto a concrete SQLite adapter.
    # The application layer depends only on LineageStorePort; this is the
    # single place where the infrastructure implementation is selected.
    from ds_agent.application.services.lineage_capture_service import (
        LineageCaptureService,
        set_lineage_service,
    )
    from ds_agent.infrastructure.persistence.lineage_store import SqliteLineageStore

    set_lineage_service(LineageCaptureService(SqliteLineageStore()))

    from ds_agent.memory.unified_store import UnifiedMemoryStore

    set_unified_memory_store(UnifiedMemoryStore())

    resolved_goal_store = goal_store or JsonGoalStore(workspace_dir)
    resolved_working_memory_store = working_memory_store or JsonWorkingMemoryStore(workspace_dir)
    resolved_approval_store = approval_store or JsonApprovalStore(workspace_dir)
    resolved_certification_store = SqliteCertificationStore.for_workspace(workspace_dir)
    task_contract_container = build_task_contract_container(
        workspace_dir,
        store=task_contract_store,
        llm_provider=provider,
    )
    hook_registry = build_hook_registry(
        max_cost_usd=max_cost_usd,
        workspace_dir=workspace_dir,
        org_policy_supplier=org_policy_supplier,
        task_contract_store=task_contract_container.store,
        mission_loader=mission_loader,
        certification_store=resolved_certification_store,
        policy_store=policy_store,
    )
    from ds_agent.tools.task_contract_tools import set_task_contract_container
    from ds_agent.tools.verifier_tool import set_verifier_container

    set_task_contract_container(task_contract_container)
    set_verifier_container(
        build_verifier_container(
            workspace_dir,
            llm_provider=provider,
        )
    )

    prompt_builder = build_prompt_builder(
        model_name=model_name,
        workspace_dir=workspace_dir,
        project_id=project_id,
        session_id=session_id,
        mode=mode,
        use_case_hint=use_case_hint,
        use_case_context=use_case_context,
        skill_hub=shared_skill_hub,
        domain_pack=domain_pack,
        goal_store=resolved_goal_store,
        working_memory_store=resolved_working_memory_store,
        task_contract_store=task_contract_container.store,
        language=language,
        authority_mode=authority_mode,
        mission_loader=mission_loader,
    )

    # Composition root: wire infrastructure adapters here
    from ds_agent.self_improve.learning_adapter import PostLearningAdapter

    post_learner = PostLearningAdapter(workspace_dir=workspace_dir)

    return DSAgent(
        provider=provider,
        tool_registry=ToolRegistry,
        budget_policy=BudgetPolicy(
            max_iterations=max_iterations,
            max_cost_usd=max_cost_usd,
        ),
        callbacks=callbacks,
        prompt_builder=prompt_builder,
        hook_registry=hook_registry,
        post_learner=post_learner,
        mode=mode,
        authority_mode=(
            None if authority_mode is None else AuthorityMode.coerce(authority_mode).value
        ),
        session_id=session_id,
        transcript_store=transcript_store,
        checkpoint_store=checkpoint_store,
        goal_store=resolved_goal_store,
        working_memory_store=resolved_working_memory_store,
        approval_store=resolved_approval_store,
        skill_hub=shared_skill_hub,
    )


def _initialize_warehouse_adapters(
    connector_configs: Mapping[str, ConnectorConfig],
) -> None:
    """Populate the shared warehouse adapter registry from connector configs."""
    from ds_agent.application.services.warehouse_service import set_warehouse_adapters
    from ds_agent.infrastructure.persistence.connector_factory import create_connector_adapters

    set_warehouse_adapters(create_connector_adapters(connector_configs))


def _build_memory_hints(workspace_dir: str) -> str:
    """Build memory hints from DomainKB if available."""
    parts: list[str] = []
    try:
        from ds_agent.memory.domain_kb import DomainKB
        from ds_agent.self_improve.memory_hints import MemoryHintBuilder

        domain_kb = DomainKB(workspace_dir + "/domain_kb.json")
        hint_builder = MemoryHintBuilder(domain_kb)
        hints = hint_builder.build_hints()
        if hints:
            parts.append(hints)
    except Exception as e:
        logger.warning("memory_hints_build_failed", error=str(e))
    try:
        from ds_agent.memory.semantic.prompt_hints import SemanticMemoryHintBuilder

        semantic_hints = SemanticMemoryHintBuilder(workspace_dir).build_hints()
        if semantic_hints:
            parts.append(semantic_hints)
    except Exception as e:
        logger.warning("semantic_memory_hints_build_failed", error=str(e))
    try:
        workspace = Path(workspace_dir).expanduser().resolve()
        if workspace.exists():
            from ds_agent.application.services.cross_session_learner import CrossSessionLearner

            recent = CrossSessionLearner.from_workspace(str(workspace)).recent_prompt_context(
                max_results=3
            )
            if recent:
                parts.append(recent)
    except Exception as e:
        logger.warning("cross_session_hints_build_failed", error=str(e))
    return "\n".join(parts)


def _build_project_context(workspace_dir: str | None, project_id: str | None) -> str:
    """Build project context from ProjectStore if available (GAP-04 fix)."""
    if not workspace_dir or not project_id:
        return ""
    try:
        from ds_agent.memory.project_store import ProjectStore

        store = ProjectStore(workspace_dir + "/projects")
        project = store.get_project(project_id)
        if not project:
            return ""
        parts = [f"Project: {project.get('name', project_id)}"]
        if project.get("task_type"):
            parts.append(f"Task type: {project['task_type']}")
        if project.get("artifacts"):
            parts.append(f"Artifacts: {len(project['artifacts'])}")
        return "\n".join(parts)
    except Exception as e:
        logger.warning("project_context_build_failed", error=str(e))
        return ""


def _normalize_domain_packs(domain_pack: str | list[str] | None) -> list[str]:
    if domain_pack is None:
        return []
    if isinstance(domain_pack, str):
        return [domain_pack]
    return [pack for pack in domain_pack if pack]
