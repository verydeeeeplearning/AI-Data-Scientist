"""DTOs for task contract boundaries."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ds_agent.domain.entities.assumption_log import AssumptionLog
from ds_agent.domain.entities.dataset_manifest import DatasetManifest
from ds_agent.domain.entities.delivery_pack import (
    DeliveryChannel,
    DeliveryPack,
    DeliveryPackStatus,
)
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.metric_spec import MetricSpec
from ds_agent.domain.entities.review_verdict import (
    ActionHint,
    ConfidenceBand,
    Issue,
    LayerResult,
    ReviewVerdict,
    VerdictCategory,
    VerdictResult,
)
from ds_agent.domain.entities.task_contract import (
    AutonomyBoundary,
    Budget,
    DataSourceGrant,
    DefinitionOfDone,
    DeliverableSpec,
    TaskContract,
    TaskContractStatus,
)
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode


class GoalBriefDraftDTO(BaseModel):
    """Input payload for creating a GoalBrief."""

    business_question: str
    ds_problem_statement: str
    hypothesis: str | None = None
    comparison_baseline: str
    decision_to_make: str
    expected_effort: str


class TaskContractDraftDTO(BaseModel):
    """Input payload for creating a task contract draft."""

    session_id: str
    contract_type: str
    business_goal: str
    goal_brief: GoalBriefDraftDTO
    required_deliverables: list[DeliverableSpec]
    allowed_data_sources: list[DataSourceGrant] = Field(default_factory=list)
    forbidden_data_patterns: list[str] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)
    autonomy: AutonomyBoundary = Field(default_factory=AutonomyBoundary)
    decision_owner: str | None = None
    decision_deadline: datetime | None = None
    definition_of_done: DefinitionOfDone | None = None
    authority: AuthorityMode | None = None
    audience: AudiencePersona | None = None
    mission: str | None = None
    created_by: str = "agent"


class TaskContractUpdateDTO(BaseModel):
    """Patch + transition request for an existing contract."""

    task_id: str
    expected_version: int = Field(ge=1)
    patch: dict[str, Any] = Field(default_factory=dict)
    transition_to: TaskContractStatus | None = None
    reason: str | None = None


class AssumptionInputDTO(BaseModel):
    """Input payload for a single assumption entry."""

    task_id: str
    statement: str
    rationale: str
    risk_level: Literal["low", "medium", "high"]
    asked_user: bool = False


class VerifyAssumptionDTO(BaseModel):
    """Input payload for marking one assumption as verified."""

    task_id: str
    entry_id: str
    expected_version: int = Field(ge=1)
    verification_note: str | None = None


class ReviewVerdictInputDTO(BaseModel):
    """Input payload for recording a review verdict."""

    task_id: str
    verdict_id: str | None = None
    category: VerdictCategory = "orchestrator"
    result: VerdictResult | None = None
    reviewer: str = "verifier"
    summary: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    run_id: str | None = None
    layers: list[LayerResult] = Field(default_factory=list)
    blocking_issues: list[Issue] = Field(default_factory=list)
    confidence: ConfidenceBand | None = None
    recommended_actions: list[ActionHint] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeliveryPackInputDTO(BaseModel):
    """Input payload for recording a delivery pack."""

    task_id: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)
    source_analysis_id: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    signed_by: str | None = None
    signature: str | None = None
    global_context: dict[str, str] = Field(default_factory=dict)
    status: DeliveryPackStatus = DeliveryPackStatus.RENDERED
    tenant: str = Field(default="default", min_length=1)


class BuildDeliveryPackDTO(BaseModel):
    """Input payload for planning a typed delivery pack from a task contract."""

    task_id: str
    audiences: list[str] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)
    source_analysis_id: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    signed_by: str | None = None
    signature: str | None = None
    global_context: dict[str, str] = Field(default_factory=dict)
    tenant: str = Field(default="default", min_length=1)


class RenderDeliveryArtifactDTO(BaseModel):
    """Input payload for rendering one artifact from a persisted delivery pack."""

    task_id: str
    artifact_id: str
    analysis: dict[str, Any] | str
    output_dir: str
    audience_profile: AudiencePersona | None = None


class DispatchDeliveryDTO(BaseModel):
    """Input payload for dispatching rendered delivery artifacts."""

    task_id: str
    artifact_ids: list[str] = Field(default_factory=list)
    channels: list[DeliveryChannel] = Field(default_factory=list)
    dry_run: bool = False
    approve_manual_review: bool = False


class ListDeliveryLogDTO(BaseModel):
    """Input payload for querying persisted delivery-dispatch logs."""

    task_id: str
    pack_id: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    channels: list[DeliveryChannel] = Field(default_factory=list)
    limit: int = Field(default=50, ge=1, le=500)


class TaskContractListItemDTO(BaseModel):
    """Compact list view of a task contract."""

    task_id: str
    status: str
    type: str
    business_goal: str
    updated_at: datetime
    version: int

    @classmethod
    def from_contract(cls, contract: TaskContract) -> TaskContractListItemDTO:
        return cls(
            task_id=contract.task_id,
            status=contract.status.value,
            type=contract.type,
            business_goal=contract.business_goal,
            updated_at=contract.updated_at,
            version=contract.version,
        )


class TaskContractViewDTO(BaseModel):
    """Detailed view returned to tools and presentation layers."""

    contract: TaskContract
    goal_brief: GoalBrief | None = None
    metric_specs: list[MetricSpec] = Field(default_factory=list)
    dataset_manifest: DatasetManifest | None = None
    assumption_log: AssumptionLog | None = None
    review_verdicts: list[ReviewVerdict] = Field(default_factory=list)
    delivery_pack: DeliveryPack | None = None
    dod_summary: list[str] = Field(default_factory=list)

    @classmethod
    def from_bundle(
        cls,
        bundle: TaskContractBundle,
        *,
        include: set[str] | None = None,
        dod_summary: list[str] | None = None,
    ) -> TaskContractViewDTO:
        include_all = include is None
        include_set = include or set()
        return cls(
            contract=bundle.contract,
            goal_brief=(bundle.goal_brief if include_all or "goal_brief" in include_set else None),
            metric_specs=(
                bundle.metric_specs if include_all or "metric_specs" in include_set else []
            ),
            dataset_manifest=(
                bundle.dataset_manifest
                if include_all or "dataset_manifest" in include_set
                else None
            ),
            assumption_log=(
                bundle.assumption_log if include_all or "assumption_log" in include_set else None
            ),
            review_verdicts=(
                bundle.review_verdicts if include_all or "review_verdicts" in include_set else []
            ),
            delivery_pack=(
                bundle.delivery_pack if include_all or "delivery_pack" in include_set else None
            ),
            dod_summary=dod_summary or [],
        )
