"""Event log model for outbound integration actions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.entities.external_reference import ExternalReference


class IntegrationEventStatus(StrEnum):
    """Persisted result state for one integration action."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    DLQ = "dlq"
    DUPLICATE = "duplicate"


class IntegrationEvent(BaseModel):
    """Audit-friendly event generated for one integration dispatch attempt."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1)
    work_object_id: str = Field(min_length=1)
    system: str = Field(min_length=1)
    action: str = Field(min_length=1)
    request_payload_hash: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    status: IntegrationEventStatus
    external_ref: ExternalReference | None = None
    attempt: int = Field(default=1, ge=1)
    latency_ms: int = Field(default=0, ge=0)
    started_at: datetime
    finished_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    policy_decision_id: str | None = None
    request_payload_json: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status in {IntegrationEventStatus.SUCCESS, IntegrationEventStatus.DUPLICATE}
