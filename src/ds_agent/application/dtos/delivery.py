"""DTOs for stakeholder communication rendering."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.entities.delivery_pack import ArtifactFormat, DeliveryChannel, NarrativeBlocks


class NarrativeVerificationResult(BaseModel):
    """Verifier result returned by audience rendering."""

    model_config = ConfigDict(frozen=True)

    narrative: NarrativeBlocks
    status: str = "pass"
    report_id: str | None = None
    flagged_claims: list[str] = Field(default_factory=list)
    rejected: bool = False
    notes: list[str] = Field(default_factory=list)


class RenderedArtifact(BaseModel):
    """Materialized artifact written to disk by the audience renderer."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str
    format: ArtifactFormat
    output_path: Path
    narrative: NarrativeBlocks
    verifier_status: str = "pass"
    verifier_report_id: str | None = None
    flagged_claims: tuple[str, ...] = ()
    chart_paths: tuple[Path, ...] = ()

    @property
    def block_count(self) -> int:
        return len(self.narrative.blocks)


class DispatchReceipt(BaseModel):
    """One channel-level dispatch attempt result."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str
    channel: DeliveryChannel
    status: Literal["sent", "blocked", "duplicate", "failed", "dry_run"]
    idempotency_key: str
    recorded_at: datetime
    reason: str | None = None
    receipt_id: str | None = None
    adapter_name: str | None = None


class DispatchDeliveryResult(BaseModel):
    """Aggregated dispatch outcome for a delivery-pack execution."""

    model_config = ConfigDict(frozen=True)

    task_id: str
    pack_id: str
    dispatch_status: Literal["dispatched", "partial", "blocked", "dry_run"]
    dry_run: bool = False
    receipts: tuple[DispatchReceipt, ...] = ()
    log_path: Path | None = None

    @property
    def sent_count(self) -> int:
        return sum(1 for receipt in self.receipts if receipt.status == "sent")

    @property
    def blocked_count(self) -> int:
        return sum(1 for receipt in self.receipts if receipt.status == "blocked")

    @property
    def failed_count(self) -> int:
        return sum(1 for receipt in self.receipts if receipt.status == "failed")

    @property
    def duplicate_count(self) -> int:
        return sum(1 for receipt in self.receipts if receipt.status == "duplicate")


class DispatchLogRecord(BaseModel):
    """One persisted delivery-log record."""

    model_config = ConfigDict(frozen=True)

    task_id: str
    pack_id: str
    artifact_id: str
    channel: DeliveryChannel
    status: Literal["sent", "blocked", "duplicate", "failed", "dry_run"]
    idempotency_key: str
    recorded_at: datetime
    reason: str | None = None
    receipt_id: str | None = None
    adapter_name: str | None = None


class DeliveryLogSummary(BaseModel):
    """Pack-level delivery summary for operator-facing log inspection."""

    model_config = ConfigDict(frozen=True)

    task_id: str
    pack_id: str
    pack_status: str
    artifact_count: int = 0
    rendered_count: int = 0
    sent: int = 0
    blocked: int = 0
    duplicate: int = 0
    failed: int = 0
    dry_run: int = 0
    last_attempt: datetime | None = None


class DeliveryLogQueryResult(BaseModel):
    """Filtered dispatch-log view for one task or pack."""

    model_config = ConfigDict(frozen=True)

    task_id: str
    pack_id: str | None = None
    log_path: Path | None = None
    records: tuple[DispatchLogRecord, ...] = ()
    summary: DeliveryLogSummary | None = None

    @property
    def returned(self) -> int:
        return len(self.records)
