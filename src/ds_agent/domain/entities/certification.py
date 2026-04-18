"""Certification entities for the autonomy control plane."""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode

_CERTIFIABLE_LEVELS = frozenset(
    {
        AuthorityMode.SHADOW,
        AuthorityMode.SUPERVISED,
        AuthorityMode.DELEGATE,
        AuthorityMode.AUTOPILOT,
    }
)


def certification_rank(level: AuthorityMode | str) -> int:
    """Return the ordering rank for certifiable authority levels."""

    resolved = _coerce_certification_level(level)
    ordered = (
        AuthorityMode.SHADOW,
        AuthorityMode.SUPERVISED,
        AuthorityMode.DELEGATE,
        AuthorityMode.AUTOPILOT,
    )
    return ordered.index(resolved)


class CertificationRequirement(BaseModel):
    """Minimum evidence required to certify one mission level."""

    model_config = ConfigDict(frozen=True)

    shadow_runs_passed: int = Field(default=0, ge=0)
    critical_violations: int = Field(default=0, ge=0)
    verifier_avg_score: float | None = Field(default=None, ge=0.0, le=1.0)
    rollback_rehearsal: bool = False
    owner_approvals: int = Field(default=0, ge=0)

    @field_validator("rollback_rehearsal", mode="before")
    @classmethod
    def _coerce_rollback_rehearsal(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        normalized = str(value or "").strip().lower()
        if normalized in {"", "false", "0", "no", "none", "not_required"}:
            return False
        if normalized in {"true", "1", "yes", "required", "passed"}:
            return True
        raise ValueError("rollback_rehearsal must be a boolean or 'passed'.")


class CertificationHistoryEntry(BaseModel):
    """One approval event captured in the mission definition."""

    model_config = ConfigDict(frozen=True)

    date: date
    level: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    evidence_ref: str | None = None


class CertificationDeprecation(BaseModel):
    """Demotion policy attached to one mission certification."""

    model_config = ConfigDict(frozen=True)

    trigger_conditions: tuple[str, ...] = Field(default_factory=tuple)
    action: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_deprecation(self) -> CertificationDeprecation:
        if not self.trigger_conditions:
            raise ValueError("trigger_conditions must contain at least one rule.")
        for condition in self.trigger_conditions:
            if not condition.strip():
                raise ValueError("trigger_conditions entries must be non-empty strings.")
        return self


class CertificationStats(BaseModel):
    """Aggregated mission evidence used to evaluate certification readiness."""

    model_config = ConfigDict(frozen=True)

    shadow_runs_passed: int = Field(default=0, ge=0)
    critical_violations: int = Field(default=0, ge=0)
    verifier_avg_score: float | None = Field(default=None, ge=0.0, le=1.0)
    rollback_rehearsal_passed: bool = False


class CertificationSpec(BaseModel):
    """Certification policy embedded inside a mission pack."""

    model_config = ConfigDict(frozen=True)

    current_level: AuthorityMode | None = None
    next_target: AuthorityMode | None = None
    autopilot_requirements: CertificationRequirement | None = None
    history: tuple[CertificationHistoryEntry, ...] = Field(default_factory=tuple)
    next_review: date | None = None
    deprecation: CertificationDeprecation | None = None

    @field_validator("current_level", "next_target", mode="after")
    @classmethod
    def _validate_levels(cls, value: AuthorityMode | None) -> AuthorityMode | None:
        if value is None:
            return None
        return _coerce_certification_level(value)

    @model_validator(mode="after")
    def _validate_progression(self) -> CertificationSpec:
        if (
            self.current_level is not None
            and self.next_target is not None
            and certification_rank(self.next_target) < certification_rank(self.current_level)
        ):
            raise ValueError("next_target must be at or above current_level.")
        return self

    def requirements(self, target_level: AuthorityMode | str) -> CertificationRequirement:
        """Return requirements for ``target_level``."""

        resolved = _coerce_certification_level(target_level)
        if resolved is AuthorityMode.AUTOPILOT:
            return self.autopilot_requirements or CertificationRequirement()
        raise ValueError(f"Unsupported certification target: {resolved.value}")

    def evaluate(
        self,
        target_level: AuthorityMode | str,
        stats: CertificationStats,
    ) -> tuple[str, ...]:
        """Return unmet requirement descriptions for ``target_level``."""

        requirement = self.requirements(target_level)
        gaps: list[str] = []
        if stats.shadow_runs_passed < requirement.shadow_runs_passed:
            gaps.append(
                "shadow_runs_passed "
                f"{stats.shadow_runs_passed}/{requirement.shadow_runs_passed}"
            )
        if stats.critical_violations > requirement.critical_violations:
            gaps.append(
                "critical_violations "
                f"{stats.critical_violations}>{requirement.critical_violations}"
            )
        if requirement.verifier_avg_score is not None:
            current_score = stats.verifier_avg_score
            if current_score is None or current_score < requirement.verifier_avg_score:
                pretty = "n/a" if current_score is None else f"{current_score:.2f}"
                gaps.append(
                    "verifier_avg_score "
                    f"{pretty}<{requirement.verifier_avg_score:.2f}"
                )
        if requirement.rollback_rehearsal and not stats.rollback_rehearsal_passed:
            gaps.append("rollback_rehearsal not passed")
        return tuple(gaps)

    def is_certified_for(self, level: AuthorityMode | str) -> bool:
        """Return whether the embedded mission level already satisfies ``level``."""

        if self.current_level is None:
            return False
        return certification_rank(self.current_level) >= certification_rank(level)


class CertificationRecord(BaseModel):
    """Persisted certification approval for one mission version."""

    model_config = ConfigDict(frozen=True)

    mission_name: str = Field(min_length=1)
    mission_version: int = Field(ge=1)
    level: AuthorityMode
    transition_from: AuthorityMode | None = None
    approved_by: tuple[str, ...] = Field(default_factory=tuple)
    approved_at: datetime
    evidence_ref: str | None = None
    next_review: date | None = None

    @field_validator("level", "transition_from", mode="after")
    @classmethod
    def _validate_record_levels(cls, value: AuthorityMode | None) -> AuthorityMode | None:
        if value is None:
            return None
        return _coerce_certification_level(value)

    @field_validator("approved_by", mode="before")
    @classmethod
    def _coerce_approved_by(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        raw_values: list[object]
        if isinstance(value, str):
            raw_values = [value]
        else:
            raw_values = (
                list(value)
                if isinstance(value, (list, tuple, set, frozenset))
                else [value]
            )
        approved_by = tuple(str(item).strip() for item in raw_values if str(item).strip())
        return approved_by

    @field_validator("approved_at", mode="after")
    @classmethod
    def _normalize_approved_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _validate_approvals(self) -> CertificationRecord:
        if not self.approved_by:
            raise ValueError("approved_by must contain at least one approver.")
        return self


class AutonomyRunStat(BaseModel):
    """Persisted mission-run metrics used for certification evaluation."""

    model_config = ConfigDict(frozen=True)

    mission_name: str = Field(min_length=1)
    mission_version: int = Field(ge=1)
    run_id: str = Field(min_length=1)
    authority: AuthorityMode
    audience: AudiencePersona
    started_at: datetime
    ended_at: datetime | None = None
    outcome: str | None = None
    verifier_score: float | None = Field(default=None, ge=0.0, le=1.0)
    violations_critical: int = Field(default=0, ge=0)
    violations_warn: int = Field(default=0, ge=0)
    rollback_rehearsal: bool = False

    @field_validator("authority", mode="after")
    @classmethod
    def _validate_stat_authority(cls, value: AuthorityMode) -> AuthorityMode:
        return _coerce_certification_level(value)

    @field_validator("started_at", "ended_at", mode="after")
    @classmethod
    def _normalize_datetimes(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def _coerce_certification_level(level: AuthorityMode | str) -> AuthorityMode:
    resolved = AuthorityMode.coerce(level)
    if resolved not in _CERTIFIABLE_LEVELS:
        raise ValueError(f"Unsupported certification level: {resolved.value}")
    return resolved
