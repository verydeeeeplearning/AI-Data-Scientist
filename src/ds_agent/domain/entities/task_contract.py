"""Task contract root entity and supporting value objects."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ds_agent.domain.entities._id_patterns import TASK_CONTRACT_ID_PATTERN
from ds_agent.domain.entities.review_verdict import ConfidenceGrade, VerdictResult
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode


class TaskContractStatus(StrEnum):
    """Lifecycle state for one explicit task delegation contract."""

    DRAFT = "draft"
    AGREED = "agreed"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    CLOSED = "closed"
    ABANDONED = "abandoned"


class DataSourceGrant(BaseModel):
    """Allowed source scope for a contract."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    warehouse: str = Field(min_length=1, description="snowflake, bigquery, local, ...")
    schema_name: str = Field(min_length=1, alias="schema")
    access_level: Literal["read_only", "read_write", "masked"] = "read_only"
    note: str | None = None


class Budget(BaseModel):
    """Explicit resource budget guardrails."""

    model_config = ConfigDict(frozen=True)

    max_compute_cost_usd: float | None = Field(default=None, ge=0)
    max_llm_cost_usd: float | None = Field(default=None, ge=0)
    max_wall_time_seconds: int | None = Field(default=None, ge=0)


class DeliverableSpec(BaseModel):
    """Expected output for one audience and format."""

    type: Literal[
        "exec_brief",
        "pm_action_memo",
        "ds_experiment_note",
        "ml_handoff_spec",
        "audit_trail",
        "ds_appendix",
        "action_proposals",
        "dashboard",
        "notebook",
        "email",
        "slack_thread",
    ]
    audience: Literal[
        "executive",
        "ds_peer",
        "peer_ds",
        "pm",
        "ml_engineer",
        "auditor",
        "junior_mentee",
        "junior_mentor",
        "ops",
        "customer",
    ]
    format: str = Field(min_length=1)
    count: int | None = Field(default=None, gt=0)
    constraints: dict[str, str] = Field(default_factory=dict)


class AutonomyBoundary(BaseModel):
    """What the agent may do, ask, and escalate."""

    agent_will_do: list[str] = Field(default_factory=list)
    agent_will_ask: list[str] = Field(default_factory=list)
    agent_will_escalate: list[str] = Field(default_factory=list)


class DefinitionOfDone(BaseModel):
    """Completion criteria for the contract."""

    class VerifierRequirements(BaseModel):
        """Optional verifier gates for closing the contract."""

        model_config = ConfigDict(frozen=True)

        min_result: VerdictResult | None = None
        min_confidence_grade: ConfidenceGrade | None = None
        require_no_blocking_issues: bool = False

    criteria: list[str] = Field(min_length=1)
    rollback_rule: str | None = None
    verifier: VerifierRequirements | None = None


class TaskContract(BaseModel):
    """Single source of truth for a delegated data-science task."""

    model_config = ConfigDict(validate_assignment=True)

    task_id: str = Field(pattern=TASK_CONTRACT_ID_PATTERN)
    session_id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    status: TaskContractStatus = TaskContractStatus.DRAFT

    business_goal: str = Field(min_length=1)
    primary_kpi_id: str | None = None
    secondary_kpi_ids: list[str] = Field(default_factory=list)
    decision_owner: str | None = None
    decision_deadline: datetime | None = None

    allowed_data_sources: list[DataSourceGrant] = Field(default_factory=list)
    forbidden_data_patterns: list[str] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)

    required_deliverables: list[DeliverableSpec] = Field(default_factory=list)
    autonomy: AutonomyBoundary = Field(default_factory=AutonomyBoundary)
    definition_of_done: DefinitionOfDone | None = None
    authority: AuthorityMode | None = None
    audience: AudiencePersona | None = None
    mission: str | None = Field(default=None, min_length=1)

    goal_brief_id: str | None = None
    dataset_manifest_id: str | None = None
    assumption_log_id: str | None = None
    delivery_pack_id: str | None = None
    metric_spec_ids: list[str] = Field(default_factory=list)
    review_verdict_ids: list[str] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime
    created_by: Literal["agent", "user"] = "agent"
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _validate_deliverables(self) -> TaskContract:
        if not self.required_deliverables:
            raise ValueError("required_deliverables must contain at least one item")
        return self

    @property
    def is_terminal(self) -> bool:
        return self.status in {TaskContractStatus.CLOSED, TaskContractStatus.ABANDONED}
