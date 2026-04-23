"""Assemble a Mission Header snapshot from active runtime state."""

from __future__ import annotations

import time
from pathlib import Path

from ds_agent.application.dtos.mission_context_dto import (
    MissionBudgetDTO,
    MissionConnectionDTO,
    MissionConstraintsDTO,
    MissionContextDTO,
    MissionDataSourceDTO,
    MissionGoalDTO,
    MissionModelDTO,
    MissionStageDTO,
)
from ds_agent.config.schema import DSAgentConfig
from ds_agent.domain.entities.goal import GoalRecord, GoalStatus
from ds_agent.domain.entities.runtime_state import RunState, RuntimeStatus
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.value_objects.quality_preset import QualityPreset, detect_quality_preset

_MISSION_STAGE_TOTAL = 4


class GetMissionContextUseCase:
    """Build one Mission Header context snapshot for a session."""

    def __init__(self, config: DSAgentConfig) -> None:
        self._config = config

    def execute(
        self,
        *,
        session_id: str,
        task_contract_bundle: TaskContractBundle | None = None,
        active_goal: GoalRecord | None = None,
        latest_run: RunState | None = None,
        active_agent: object | None = None,
    ) -> MissionContextDTO:
        primary_model = self._resolve_primary_model(active_agent)
        fallback_models = list(self._config.provider.fallback_models)

        return MissionContextDTO(
            goal=self._build_goal(task_contract_bundle, active_goal),
            dataSources=self._build_data_sources(task_contract_bundle),
            deliverables=self._build_deliverables(task_contract_bundle),
            constraints=self._build_constraints(task_contract_bundle, primary_model),
            stage=self._build_stage(task_contract_bundle, active_goal, latest_run),
            mode=self._config.agent.mode,
            model=self._build_model(primary_model, fallback_models),
            budget=self._build_budget(active_agent, latest_run),
            connection=self._build_connection(active_agent, latest_run),
        )

    def _build_goal(
        self,
        task_contract_bundle: TaskContractBundle | None,
        active_goal: GoalRecord | None,
    ) -> MissionGoalDTO:
        title = "No active mission"
        success_criteria: list[str] = []

        if task_contract_bundle is not None:
            title = task_contract_bundle.contract.business_goal
            definition_of_done = task_contract_bundle.contract.definition_of_done
            if definition_of_done is not None:
                success_criteria = list(definition_of_done.criteria)
            elif task_contract_bundle.contract.required_deliverables:
                success_criteria = [
                    (
                        f"Deliver {item.type} for {item.audience}"
                        if item.format == ""
                        else f"Deliver {item.type} for {item.audience} ({item.format})"
                    )
                    for item in task_contract_bundle.contract.required_deliverables
                ]
        elif active_goal is not None:
            title = active_goal.summary or active_goal.detail or title

        return MissionGoalDTO(title=title, successCriteria=success_criteria)

    def _build_data_sources(
        self,
        task_contract_bundle: TaskContractBundle | None,
    ) -> list[MissionDataSourceDTO]:
        if task_contract_bundle is None:
            return []

        items: list[MissionDataSourceDTO] = []
        seen: set[str] = set()

        dataset_manifest = task_contract_bundle.dataset_manifest
        if dataset_manifest is not None:
            for entry in dataset_manifest.entries:
                label = entry.dataset_ref
                if label in seen:
                    continue
                seen.add(label)
                items.append(
                    MissionDataSourceDTO(
                        type=self._infer_source_type(label),  # type: ignore[arg-type]
                        label=label,
                        rowCount=entry.row_count,
                    )
                )

        for grant in task_contract_bundle.contract.allowed_data_sources:
            label = f"{grant.warehouse}.{grant.schema_name}"
            if label in seen:
                continue
            seen.add(label)
            items.append(
                MissionDataSourceDTO(
                    type="database",
                    label=label,
                    rowCount=None,
                )
            )

        return items

    @staticmethod
    def _build_deliverables(task_contract_bundle: TaskContractBundle | None) -> list[str]:
        if task_contract_bundle is None:
            return []

        deliverables: list[str] = []
        seen: set[str] = set()
        for item in task_contract_bundle.contract.required_deliverables:
            if item.type in seen:
                continue
            seen.add(item.type)
            deliverables.append(item.type)
        return deliverables

    def _build_constraints(
        self,
        task_contract_bundle: TaskContractBundle | None,
        primary_model: str,
    ) -> MissionConstraintsDTO:
        authority = None
        if task_contract_bundle is not None and task_contract_bundle.contract.authority is not None:
            authority = task_contract_bundle.contract.authority.value

        requires_approval = authority in {"shadow", "supervised", "freeze"}
        if authority is None:
            requires_approval = self._config.agent.mode != "auto"

        return MissionConstraintsDTO(
            language=self._config.agent.language,
            requiresApproval=requires_approval,
            localOnlyModel=primary_model.startswith("ollama/"),
        )

    @staticmethod
    def _build_stage(
        task_contract_bundle: TaskContractBundle | None,
        active_goal: GoalRecord | None,
        latest_run: RunState | None,
    ) -> MissionStageDTO:
        if task_contract_bundle is not None:
            status = task_contract_bundle.contract.status.value
            if status == "draft":
                return MissionStageDTO(
                    current=1,
                    total=_MISSION_STAGE_TOTAL,
                    label="Mission drafting",
                )
            if status == "agreed":
                return MissionStageDTO(
                    current=1,
                    total=_MISSION_STAGE_TOTAL,
                    label="Mission agreed",
                )
            if status == "in_progress":
                label = (
                    "Analysis running"
                    if latest_run is not None and latest_run.status == RuntimeStatus.RUNNING
                    else "Execution in progress"
                )
                return MissionStageDTO(current=2, total=_MISSION_STAGE_TOTAL, label=label)
            if status == "review":
                return MissionStageDTO(
                    current=3,
                    total=_MISSION_STAGE_TOTAL,
                    label="Awaiting review",
                )
            if status == "closed":
                return MissionStageDTO(current=4, total=_MISSION_STAGE_TOTAL, label="Completed")
            return MissionStageDTO(current=4, total=_MISSION_STAGE_TOTAL, label="Stopped")

        if active_goal is not None:
            if active_goal.status == GoalStatus.PENDING:
                return MissionStageDTO(current=1, total=_MISSION_STAGE_TOTAL, label="Goal captured")
            if active_goal.status == GoalStatus.IN_PROGRESS:
                return MissionStageDTO(
                    current=2,
                    total=_MISSION_STAGE_TOTAL,
                    label="Analysis running",
                )
            if active_goal.status == GoalStatus.BLOCKED:
                return MissionStageDTO(current=3, total=_MISSION_STAGE_TOTAL, label="Blocked")
            if active_goal.status == GoalStatus.COMPLETED:
                return MissionStageDTO(current=4, total=_MISSION_STAGE_TOTAL, label="Completed")
            return MissionStageDTO(current=4, total=_MISSION_STAGE_TOTAL, label="Cancelled")

        if latest_run is not None:
            if latest_run.status == RuntimeStatus.RUNNING:
                return MissionStageDTO(
                    current=2,
                    total=_MISSION_STAGE_TOTAL,
                    label="Analysis running",
                )
            if latest_run.status == RuntimeStatus.SUCCEEDED:
                return MissionStageDTO(current=4, total=_MISSION_STAGE_TOTAL, label="Completed")
            if latest_run.status == RuntimeStatus.CANCELLED:
                return MissionStageDTO(current=3, total=_MISSION_STAGE_TOTAL, label="Cancelled")
            return MissionStageDTO(current=3, total=_MISSION_STAGE_TOTAL, label="Needs attention")

        return MissionStageDTO(current=1, total=_MISSION_STAGE_TOTAL, label="Ready")

    def _build_model(
        self,
        primary_model: str,
        fallback_models: list[str],
    ) -> MissionModelDTO:
        preset = detect_quality_preset(primary_model, fallback_models)
        return MissionModelDTO(
            primary=primary_model,
            fallbacks=fallback_models,
            capabilities=self._capabilities_for_model(primary_model, preset),
        )

    def _build_budget(
        self,
        active_agent: object | None,
        latest_run: RunState | None,
    ) -> MissionBudgetDTO:
        spent_usd = 0.0
        limit_usd = float(self._config.provider.max_budget_usd)
        elapsed_sec = 0.0

        budget = getattr(active_agent, "_budget", None)
        get_summary = getattr(budget, "get_summary", None)
        if callable(get_summary):
            summary = get_summary()
            spent_usd = float(summary.get("total_cost_usd", 0.0) or 0.0)
            elapsed_sec = float(summary.get("wall_time_seconds", 0.0) or 0.0)
            limit_usd = float(summary.get("max_cost_usd", limit_usd) or limit_usd)
        elif latest_run is not None:
            spent_usd = float(latest_run.cost_usd)
            finished_at = latest_run.finished_at
            if latest_run.status == RuntimeStatus.RUNNING or finished_at is None:
                finished_at = time.time()
            elapsed_sec = max(0.0, float(finished_at) - latest_run.started_at)

        threshold_ratio = float(self._config.provider.budget_warning_threshold_pct) / 100.0
        near_limit = limit_usd > 0 and (spent_usd / limit_usd) >= threshold_ratio
        return MissionBudgetDTO(
            spentUsd=round(spent_usd, 4),
            limitUsd=round(limit_usd, 4),
            elapsedSec=round(elapsed_sec, 3),
            nearLimit=near_limit,
        )

    @staticmethod
    def _build_connection(
        active_agent: object | None,
        latest_run: RunState | None,
    ) -> MissionConnectionDTO:
        if active_agent is not None:
            return MissionConnectionDTO(state="connected", latencyMs=None)
        if latest_run is not None and latest_run.status == RuntimeStatus.RUNNING:
            return MissionConnectionDTO(state="reconnecting", latencyMs=None)
        return MissionConnectionDTO(state="disconnected", latencyMs=None)

    def _resolve_primary_model(self, active_agent: object | None) -> str:
        provider = getattr(active_agent, "_provider", None)
        get_model_info = getattr(provider, "get_model_info", None)
        if callable(get_model_info):
            try:
                model_info = get_model_info()
            except Exception:
                model_info = None
            model_id = getattr(model_info, "model_id", None)
            if isinstance(model_id, str) and model_id.strip():
                return model_id
        return self._config.provider.default_model

    @staticmethod
    def _infer_source_type(label: str) -> str:
        normalized = label.strip().lower()
        if normalized.startswith("http://") or normalized.startswith("https://"):
            return "api"
        if Path(normalized).suffix in {
            ".csv",
            ".json",
            ".jsonl",
            ".parquet",
            ".pq",
            ".xlsx",
            ".xls",
        }:
            return "file"
        return "database"

    @staticmethod
    def _capabilities_for_model(primary_model: str, preset: QualityPreset) -> list[str]:
        if primary_model.startswith("ollama/"):
            return ["local_execution", "offline_ready"]
        if preset == QualityPreset.FAST:
            return ["fast_turnaround", "lower_cost"]
        if preset == QualityPreset.BEST_QUALITY:
            return ["deep_reasoning", "richer_reports"]
        if preset == QualityPreset.BALANCED:
            return ["balanced_reasoning", "recommended_default"]
        return []
