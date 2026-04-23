"""Domain entity for session-scoped working memory."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ds_agent.domain.value_objects.analysis_stage import AnalysisStage


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
    current_stage: AnalysisStage | None = None
    stage_entered_at: float | None = None
    updated_at: float = field(default_factory=time.time)
    pending_verifier_remediation: list[dict] | None = None
