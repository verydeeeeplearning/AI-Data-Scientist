"""Organizational context domain models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ds_agent.memory.semantic.domain._normalization import normalize_string_list

CalendarEventType = Literal["fiscal_period", "campaign", "freeze", "launch", "holiday"]
DecisionOutcome = Literal["approved", "rejected", "deferred"]
NegativeKnowledgeSource = Literal["human", "agent_self_correction", "retrospective"]


class CalendarEvent(BaseModel):
    """One org-level event that can change query interpretation."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1)
    type: CalendarEventType
    name: str = Field(min_length=1)
    start_date: date
    end_date: date
    description: str = Field(min_length=1)
    impact_hint: str | None = None

    @model_validator(mode="after")
    def _validate_range(self) -> CalendarEvent:
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class TeamOwnership(BaseModel):
    """Ownership mapping for teams, tables, and metrics."""

    model_config = ConfigDict(frozen=True)

    team: str = Field(min_length=1)
    contact: str = Field(min_length=1)
    owned_metrics: list[str] = Field(default_factory=list)
    owned_tables: list[str] = Field(default_factory=list)
    approver_chain: list[str] = Field(default_factory=list)

    @field_validator("owned_metrics", "owned_tables", "approver_chain", mode="before")
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return normalize_string_list(value)


class DecisionLogEntry(BaseModel):
    """Human decision trace tied to metrics and verified queries."""

    model_config = ConfigDict(frozen=True)

    decision_id: str = Field(min_length=1)
    date: date
    summary: str = Field(min_length=1)
    context: str = Field(min_length=1)
    metrics_used: list[str] = Field(default_factory=list)
    verified_query_ids: list[str] = Field(default_factory=list)
    outcome: DecisionOutcome
    rationale: str = Field(min_length=1)

    @field_validator("metrics_used", "verified_query_ids", mode="before")
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return normalize_string_list(value)


class NegativeKnowledge(BaseModel):
    """Structured memory for a known-bad semantic interpretation."""

    model_config = ConfigDict(frozen=True)

    nk_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    wrong_approach: str = Field(min_length=1)
    why_wrong: str = Field(min_length=1)
    correct_approach: str = Field(min_length=1)
    recorded_at: datetime
    recorded_by: NegativeKnowledgeSource
    references: list[str] = Field(default_factory=list)

    @field_validator("references", mode="before")
    @classmethod
    def _normalize_refs(cls, value: object) -> list[str]:
        return normalize_string_list(value)

    @model_validator(mode="after")
    def _validate_approaches(self) -> NegativeKnowledge:
        if self.wrong_approach.strip() == self.correct_approach.strip():
            raise ValueError("wrong_approach and correct_approach must differ")
        return self

