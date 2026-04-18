"""Ports for persisted session transcript and checkpoint state."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.goal import GoalRecord, GoalStatus
from ds_agent.domain.entities.messages import ChatMessage
from ds_agent.domain.entities.session_checkpoint import SessionCheckpoint
from ds_agent.domain.entities.working_memory import SessionWorkingMemory


@runtime_checkable
class TranscriptStore(Protocol):
    """Persistent transcript storage for completed or latest chat history."""

    def load_messages(self, session_id: str, limit: int | None = None) -> list[ChatMessage]: ...

    def replace_messages(self, session_id: str, messages: list[ChatMessage]) -> None: ...


@runtime_checkable
class CheckpointStore(Protocol):
    """Persistent storage for in-progress session state."""

    def load(self, session_id: str) -> SessionCheckpoint | None: ...

    def save(self, checkpoint: SessionCheckpoint) -> None: ...

    def clear(self, session_id: str) -> None: ...


@runtime_checkable
class GoalStore(Protocol):
    """Persistent storage for session goals."""

    def get_active_goal(self, session_id: str) -> GoalRecord | None: ...

    def list_goals(self, session_id: str) -> list[GoalRecord]: ...

    def ensure_from_message(
        self,
        session_id: str,
        message: str,
        run_id: str | None = None,
    ) -> GoalRecord: ...

    def mark_status(
        self,
        session_id: str,
        goal_id: str,
        status: GoalStatus,
        *,
        run_id: str | None = None,
        note: str | None = None,
        blocked_reason: str | None = None,
    ) -> GoalRecord | None: ...


@runtime_checkable
class WorkingMemoryStore(Protocol):
    """Persistent short-horizon working memory for a session."""

    def load(self, session_id: str) -> SessionWorkingMemory | None: ...

    def save(self, memory: SessionWorkingMemory) -> None: ...
