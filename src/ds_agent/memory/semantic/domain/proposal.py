"""Proposal queue domain models for autonomous semantic write-back."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SemanticProposalType(StrEnum):
    """Kinds of semantic changes an agent can propose."""

    METRIC_ALIAS = "metric_alias"
    GLOSSARY_TERM = "glossary_term"
    VERIFIED_QUERY = "verified_query"
    NEGATIVE_KNOWLEDGE = "negative_knowledge"
    TABLE_TRUST_PATCH = "table_trust_patch"
    METRIC_REVIEW_REQUEST = "metric_review_request"


class SemanticProposalStatus(StrEnum):
    """Lifecycle state for a semantic proposal."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    EXPIRED = "expired"

    def can_transition_to(
        self,
        target: SemanticProposalStatus,
        *,
        auto_apply_eligible: bool,
    ) -> bool:
        """Validate lifecycle transitions for proposal review."""

        if self == target:
            return True
        allowed: dict[SemanticProposalStatus, set[SemanticProposalStatus]] = {
            SemanticProposalStatus.PENDING: {
                SemanticProposalStatus.APPROVED,
                SemanticProposalStatus.REJECTED,
                SemanticProposalStatus.EXPIRED,
            },
            SemanticProposalStatus.APPROVED: {
                SemanticProposalStatus.APPLIED,
                SemanticProposalStatus.EXPIRED,
            },
            SemanticProposalStatus.REJECTED: set(),
            SemanticProposalStatus.APPLIED: set(),
            SemanticProposalStatus.EXPIRED: set(),
        }
        if auto_apply_eligible and self == SemanticProposalStatus.PENDING:
            allowed[self].add(SemanticProposalStatus.APPLIED)
        return target in allowed[self]


class SemanticProposal(BaseModel):
    """Pending semantic-memory write created by agent or human review."""

    model_config = ConfigDict(frozen=True)

    proposal_id: str = Field(min_length=1)
    proposal_type: SemanticProposalType
    status: SemanticProposalStatus = SemanticProposalStatus.PENDING
    source_run_id: str | None = Field(default=None, min_length=1)
    source_session_id: str | None = Field(default=None, min_length=1)
    source_tool_name: str | None = Field(default=None, min_length=1)
    target_id: str | None = Field(default=None, min_length=1)
    summary: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    risk: Literal["low", "medium", "high"] = "medium"
    proposed_by: Literal["agent", "human", "adapter_sync"] = "agent"
    auto_apply_eligible: bool = False
    created_at: datetime
    expires_at: datetime | None = None
    reviewed_by: str | None = Field(default=None, min_length=1)
    reviewed_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_review_metadata(self) -> SemanticProposal:
        if self.status in {
            SemanticProposalStatus.APPROVED,
            SemanticProposalStatus.REJECTED,
            SemanticProposalStatus.APPLIED,
        } and (not self.reviewed_by or self.reviewed_at is None):
            raise ValueError("review metadata is required for reviewed proposals")
        return self

    def transition_to(
        self,
        target: SemanticProposalStatus,
        *,
        reviewed_by: str | None = None,
        reviewed_at: datetime | None = None,
    ) -> SemanticProposal:
        """Return a validated copy of the proposal in a new lifecycle state."""

        if not self.status.can_transition_to(
            target,
            auto_apply_eligible=self.auto_apply_eligible,
        ):
            raise ValueError(
                f"proposal transition from {self.status.value} to {target.value} is not allowed"
            )

        update: dict[str, object] = {"status": target}
        if reviewed_by is not None:
            update["reviewed_by"] = reviewed_by
        if reviewed_at is not None:
            update["reviewed_at"] = reviewed_at
        return self.model_copy(update=update)
