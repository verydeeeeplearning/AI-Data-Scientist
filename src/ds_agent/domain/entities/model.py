"""Decision OS model-registry entities."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.entities.feature import FeatureRef

ArtifactFormat = Literal["pickle", "onnx", "torchscript", "sql", "json"]
ServingRuntime = Literal["batch", "online", "embedded"]
ModelAlias = Literal["challenger", "champion", "canary", "retired"]


class ModelArtifact(BaseModel):
    """Artifact metadata for one registered model version."""

    model_config = ConfigDict(frozen=True)

    uri: str = Field(min_length=1)
    format: ArtifactFormat
    size_bytes: int = Field(ge=0)
    checksum: str = Field(min_length=1)


class ServingConfig(BaseModel):
    """Serving-side metadata attached to a registered model version."""

    model_config = ConfigDict(frozen=True)

    runtime: ServingRuntime
    input_schema: dict[str, object] = Field(default_factory=dict)
    output_schema: dict[str, object] = Field(default_factory=dict)
    feature_refs: list[FeatureRef] = Field(default_factory=list)
    latency_budget_ms: int | None = Field(default=None, ge=0)
    throughput_budget_qps: int | None = Field(default=None, ge=0)


class Model(BaseModel):
    """Registered model lineage tracked by Decision OS."""

    model_config = ConfigDict(frozen=True)

    model_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    alias: ModelAlias
    lineage_run_id: str = Field(min_length=1)
    artifact: ModelArtifact
    serving: ServingConfig
    created_at: datetime
    promoted_at: datetime | None = None
    retired_at: datetime | None = None
    description: str = Field(min_length=1)
