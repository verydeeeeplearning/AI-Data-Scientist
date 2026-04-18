"""Memory domain entity.

Represents a persistent memory entry with type, confidence decay,
and metadata. Domain layer — no external dependencies.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class MemoryType(StrEnum):
    """Memory hierarchy levels."""

    SESSION = "session"  # Current session only
    PROJECT = "project"  # Per-project knowledge
    DOMAIN = "domain"  # Cross-project domain knowledge
    GLOBAL = "global"  # Organization-wide knowledge


@dataclass
class MemoryEntry:
    """A single memory entry with confidence decay support.

    Confidence decays as: effective_confidence = confidence * (0.95 ^ months_since_update)
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: MemoryType = MemoryType.PROJECT
    key: str = ""
    content: str = ""
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    source_session_id: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def effective_confidence(self) -> float:
        """Confidence with time decay applied (0.95^months)."""
        months_elapsed = (time.time() - self.updated_at) / (30 * 24 * 3600)
        decay: float = 0.95 ** months_elapsed
        return self.confidence * decay

    @property
    def is_stale(self) -> bool:
        """True if effective confidence has dropped below usable threshold."""
        return self.effective_confidence < 0.3
