"""DTOs shared by verifier orchestration boundaries."""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.entities.review_verdict import LayerName
from ds_agent.domain.entities.task_contract import TaskContract


def _default_enabled_layers() -> list[LayerName]:
    return cast(
        list[LayerName],
        ["statistical", "data", "policy", "narrative"],
    )


class EvidenceRef(BaseModel):
    """Compact pointer to evidence used by the narrative layer."""

    artifact_id: str = Field(min_length=1)
    excerpt: str | None = None
    locator: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerifierConfig(BaseModel):
    """Runtime knobs for verifier execution."""

    model_config = ConfigDict(validate_assignment=True)

    statistical_timeout_s: int = Field(default=60, gt=0)
    data_timeout_s: int = Field(default=30, gt=0)
    policy_timeout_s: int = Field(default=15, gt=0)
    narrative_timeout_s: int = Field(default=45, gt=0)
    enabled_layers: list[LayerName] = Field(
        default_factory=_default_enabled_layers,
    )
    narrative_enabled: bool = True
    shadow_mode: bool = False


class VerifierContext(BaseModel):
    """Execution context passed to verifier layers and checks."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str = Field(min_length=1)
    task_contract: TaskContract
    artifacts: dict[str, Any] = Field(default_factory=dict)
    run_log: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    config: VerifierConfig = Field(default_factory=VerifierConfig)
    workspace_path: str | None = None
