"""Dataset manifest entity for task contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ds_agent.domain.entities._id_patterns import DATASET_MANIFEST_ID_PATTERN


class DatasetEntry(BaseModel):
    """One dataset referenced by the task."""

    dataset_ref: str = Field(min_length=1)
    row_count: int | None = Field(default=None, ge=0)
    schema_fingerprint: str | None = None
    freshness_seconds: int | None = Field(default=None, ge=0)
    trust_grade: Literal["gold", "silver", "bronze", "unknown"] = "unknown"
    access_level: Literal["read_only", "read_write", "masked"] = "read_only"
    notes: str | None = None


class DatasetManifest(BaseModel):
    """Dataset inventory loaded during execution."""

    manifest_id: str = Field(pattern=DATASET_MANIFEST_ID_PATTERN)
    task_id: str = Field(min_length=1)
    entries: list[DatasetEntry] = Field(default_factory=list)
    total_rows: int | None = Field(default=None, ge=0)
    generated_at: datetime
