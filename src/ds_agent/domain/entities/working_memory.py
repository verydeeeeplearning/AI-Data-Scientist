"""Domain entity for session-scoped working memory."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class SessionWorkingMemory:
    """Short-horizon runtime memory for the current active goal."""

    session_id: str
    active_goal_id: str | None = None
    last_run_id: str | None = None
    last_user_message: str | None = None
    current_summary: str = ""
    next_step: str = ""
    pending_questions: list[str] = field(default_factory=list)
    last_reflection: str = ""
    recovery_note: str | None = None
    updated_at: float = field(default_factory=time.time)
