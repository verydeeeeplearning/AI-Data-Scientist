"""Domain entities for end-to-end lineage capture."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class LineageRecordType(StrEnum):
    """Supported lineage record categories."""

    DATASET = "dataset"
    FEATURE = "feature"
    MODEL = "model"
    EVALUATION = "evaluation"
    DEPLOYMENT = "deployment"
    DECISION = "decision"


@dataclass(frozen=True, slots=True)
class LineageRecord:
    """A single lineage record linked to a parent record when applicable."""

    record_type: LineageRecordType
    content: dict[str, object]
    session_id: str | None = None
    parent_id: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
