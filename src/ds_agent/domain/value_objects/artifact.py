"""Value objects for generated communication artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ArtifactType(StrEnum):
    """Supported artifact families."""

    NOTEBOOK = "notebook"
    MEMO = "memo"
    DASHBOARD = "dashboard"
    SQL = "sql"
    MODEL_CARD = "model_card"
    SLIDE = "slide"


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    """Specification passed to artifact generators."""

    artifact_type: ArtifactType
    format: str = "markdown"
    content_sections: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
