"""Domain entity for persisted in-progress session checkpoints."""

from __future__ import annotations

from dataclasses import dataclass, field

from ds_agent.domain.entities.messages import ChatMessage


@dataclass
class SessionCheckpoint:
    """Serializable snapshot of an in-progress agent session."""

    session_id: str
    step: int
    messages: list[ChatMessage] = field(default_factory=list)
    updated_at: float = 0.0
