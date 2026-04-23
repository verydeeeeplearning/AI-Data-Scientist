"""Domain entities for persisted session checkpoints."""

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


@dataclass(slots=True)
class NamedCheckpoint:
    """Operator-named checkpoint pointing at a session's transcript step.

    A named checkpoint is a sibling concept to the implicit per-session
    ``SessionCheckpoint``: it captures a stable, human-meaningful save point
    that can be referenced by ``id`` for branching or rerun flows. The agent
    state itself remains addressed by ``session_id`` (``agent_state_ref``);
    only the metadata + the transcript step pointer live in this entity.
    """

    id: str
    session_id: str
    name: str
    created_at: float
    transcript_step: int
    description: str | None = None

    @property
    def agent_state_ref(self) -> str:
        """Stable reference to the agent state this checkpoint points at.

        Currently the agent state is keyed by ``session_id``; we expose this
        as a separate property so callers can treat it opaquely (the indirection
        becomes useful when agent state moves out of the session registry).
        """
        return self.session_id
