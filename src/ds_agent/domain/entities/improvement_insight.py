"""Cross-session improvement insight entity."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ds_agent.domain.entities.memory import MemoryEntry, MemoryType


@dataclass(frozen=True)
class ImprovementInsight:
    """Reusable lesson extracted from prior projects."""

    category: str
    summary: str
    tags: list[str]
    confidence: float
    source_project_id: str
    created_at: float = field(default_factory=time.time)

    def to_memory_entry(self, key: str) -> MemoryEntry:
        return MemoryEntry(
            type=MemoryType.PROJECT,
            key=key,
            content=self.summary,
            tags=self.tags,
            confidence=self.confidence,
            source_session_id=self.source_project_id,
            created_at=self.created_at,
            updated_at=self.created_at,
        )
