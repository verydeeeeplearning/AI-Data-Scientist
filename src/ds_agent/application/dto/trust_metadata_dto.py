"""DTOs for trust metadata projection."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BadgeStatus = Literal["green", "yellow", "red", "gray", "none"]


class TrustDataWindowDTO(BaseModel):
    """Observed time window behind the trust projection."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    start: str = Field(min_length=1)
    end: str = Field(min_length=1)
    days: int = Field(ge=0)


class TrustModelDTO(BaseModel):
    """Model projection used by the trust strip."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    primary: str = Field(min_length=1)
    fallback_occurred: bool = Field(alias="fallbackOccurred")


class TrustVerifierDTO(BaseModel):
    """Verifier badge projection."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    status: BadgeStatus
    passed: int = Field(ge=0)
    total: int = Field(ge=0)
    details: list[str] = Field(default_factory=list)


class TrustLineageDTO(BaseModel):
    """Lineage badge projection."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    status: Literal["captured", "incomplete"]
    ancestor_count: int = Field(alias="ancestorCount", ge=0)


class TrustFallbackDTO(BaseModel):
    """Provider fallback projection."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    occurred: bool
    from_model: str | None = Field(default=None, alias="from")
    to_model: str | None = Field(default=None, alias="to")
    fallback_id: str | None = Field(default=None, alias="fallbackId")
    event_count: int = Field(default=0, alias="eventCount", ge=0)
    summary: str | None = None
    status: Literal["warning"] | None = None


class TrustApprovalDTO(BaseModel):
    """Approval badge projection."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    required: bool
    approval_id: str | None = Field(default=None, alias="approvalId")
    approval_status: str | None = Field(default=None, alias="approvalStatus")
    approved_by: str | None = Field(default=None, alias="approvedBy")


class TrustDriftDTO(BaseModel):
    """Drift badge projection."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    status: BadgeStatus
    psi: float | None = None


class TrustSandboxDTO(BaseModel):
    """Sandbox-breach projection."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    violation_occurred: bool = Field(alias="violationOccurred")
    event_id: str | None = Field(default=None, alias="eventId")
    event_count: int = Field(default=0, alias="eventCount", ge=0)
    summary: str | None = None


class TrustConfidenceDTO(BaseModel):
    """Confidence projection used for detail-on-demand copy."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    level: Literal["high", "medium", "low"]
    assumptions: list[str] = Field(default_factory=list)


class TrustCertificationDTO(BaseModel):
    """Optional certification projection."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str = Field(min_length=1)
    level: Literal["platinum", "gold", "silver"]


class TrustMetadataDTO(BaseModel):
    """Trust layer metadata projected to the frontend."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    result_id: str = Field(alias="resultId", min_length=1)
    data_window: TrustDataWindowDTO | None = Field(default=None, alias="dataWindow")
    model: TrustModelDTO
    verifier: TrustVerifierDTO
    lineage: TrustLineageDTO
    fallback: TrustFallbackDTO
    approval: TrustApprovalDTO
    drift: TrustDriftDTO
    sandbox: TrustSandboxDTO
    confidence: TrustConfidenceDTO
    certification: TrustCertificationDTO | None = None
