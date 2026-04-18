"""Backtracking domain value objects.

Defines backtrack decisions and previous attempt records.
Domain layer — no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PreviousAttempt:
    """Record of a previous attempt before backtracking."""

    stage: str
    metrics: dict[str, float]
    reason: str


@dataclass(frozen=True, slots=True)
class BacktrackDecision:
    """Immutable decision for workflow backtracking.

    Produced when model performance is below baseline or expectations,
    indicating which stage to rewind to and why.
    """

    target_stage: str
    reason: str
    previous_attempts: tuple[PreviousAttempt, ...]
    should_stop: bool = False

    @property
    def backtrack_count(self) -> int:
        return len(self.previous_attempts)
