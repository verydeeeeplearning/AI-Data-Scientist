"""DTOs for uploaded-file schema preview responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SuggestedActionDTO(BaseModel):
    """UI-facing suggested follow-up action for one uploaded file."""

    model_config = ConfigDict(populate_by_name=True)

    id: Literal["run_eda", "baseline_after_target", "validate_schema"]
    label: str
    description: str
    icon: str
    requires_target: bool = Field(alias="requiresTarget")


class SuggestedTargetDTO(BaseModel):
    """Heuristic target-column suggestion."""

    model_config = ConfigDict(populate_by_name=True)

    column_name: str = Field(alias="columnName")
    confidence: Literal["high", "medium", "low"]
    reason: str


class DataQualityDTO(BaseModel):
    """Quick-scan quality signals derived from the head sample."""

    model_config = ConfigDict(populate_by_name=True)

    missing_ratio: float = Field(alias="missingRatio")
    duplicate_row_ratio: float = Field(alias="duplicateRowRatio")
    outlier_columns: list[str] = Field(default_factory=list, alias="outlierColumns")


class ColumnInfoDTO(BaseModel):
    """One previewed column's schema summary."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    dtype: Literal["int", "float", "string", "datetime", "bool", "category", "unknown"]
    null_count: int = Field(alias="nullCount")
    unique_count: int | None = Field(default=None, alias="uniqueCount")
    sample_values: list[object] = Field(default_factory=list, alias="sampleValues")


class SchemaPreviewDTO(BaseModel):
    """Head-only preview payload returned after upload."""

    model_config = ConfigDict(populate_by_name=True)

    file_id: str = Field(alias="fileId")
    workspace_path: str = Field(alias="workspacePath")
    file_name: str = Field(alias="fileName")
    size_bytes: int = Field(alias="sizeBytes")
    mime_type: str = Field(alias="mimeType")
    format: Literal["csv", "parquet", "excel", "json", "jsonl", "unknown"]
    row_count_estimate: int | None = Field(default=None, alias="rowCountEstimate")
    columns: list[ColumnInfoDTO] = Field(default_factory=list)
    sample_rows: list[dict[str, object]] = Field(default_factory=list, alias="sampleRows")
    data_quality: DataQualityDTO = Field(alias="dataQuality")
    suggested_target: SuggestedTargetDTO | None = Field(default=None, alias="suggestedTarget")
    suggested_actions: list[SuggestedActionDTO] = Field(
        default_factory=list,
        alias="suggestedActions",
    )
