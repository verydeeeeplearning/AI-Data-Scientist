"""Shadow-mode comparison entities for legacy hook vs verifier decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ds_agent.domain.entities._id_patterns import SHADOW_COMPARISON_ID_PATTERN

LegacyShadowState = Literal["triggered", "clear", "not_applicable"]
ShadowMismatchKind = Literal["legacy_only", "verifier_only", "agreement", "not_applicable"]


class ShadowComparisonItem(BaseModel):
    """One mapped legacy signal compared with one or more verifier checks."""

    model_config = ConfigDict(validate_assignment=True)

    comparison_key: str = Field(min_length=1)
    legacy_source: str = Field(min_length=1)
    verifier_targets: list[str] = Field(default_factory=list)
    applicable: bool = True
    legacy_state: LegacyShadowState = "not_applicable"
    verifier_state: LegacyShadowState = "not_applicable"
    matches: bool = False
    mismatch_kind: ShadowMismatchKind = "not_applicable"
    legacy_evidence: list[dict[str, Any]] = Field(default_factory=list)
    verifier_evidence: list[dict[str, Any]] = Field(default_factory=list)
    note: str | None = None

    @model_validator(mode="after")
    def _normalize(self) -> ShadowComparisonItem:
        if not self.applicable:
            object.__setattr__(self, "legacy_state", "not_applicable")
            object.__setattr__(self, "verifier_state", "not_applicable")
            object.__setattr__(self, "matches", False)
            object.__setattr__(self, "mismatch_kind", "not_applicable")
            return self
        matches = self.legacy_state == self.verifier_state
        object.__setattr__(self, "matches", matches)
        if matches:
            object.__setattr__(self, "mismatch_kind", "agreement")
        elif self.legacy_state == "triggered":
            object.__setattr__(self, "mismatch_kind", "legacy_only")
        else:
            object.__setattr__(self, "mismatch_kind", "verifier_only")
        return self


class ShadowComparisonRecord(BaseModel):
    """Persisted diff log between legacy hook signals and verifier verdicts."""

    model_config = ConfigDict(validate_assignment=True)

    comparison_id: str = Field(pattern=SHADOW_COMPARISON_ID_PATTERN)
    verdict_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    run_id: str | None = None
    session_id: str | None = None
    created_at: datetime
    items: list[ShadowComparisonItem] = Field(default_factory=list)
    applicable_count: int = Field(default=0, ge=0)
    mismatch_count: int = Field(default=0, ge=0)
    match_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalize(self) -> ShadowComparisonRecord:
        applicable_items = [item for item in self.items if item.applicable]
        applicable_count = len(applicable_items)
        mismatch_count = sum(1 for item in applicable_items if not item.matches)
        match_rate = (
            1.0 - (mismatch_count / applicable_count)
            if applicable_count > 0
            else 0.0
        )
        object.__setattr__(self, "applicable_count", applicable_count)
        object.__setattr__(self, "mismatch_count", mismatch_count)
        object.__setattr__(self, "match_rate", round(match_rate, 6))
        return self
