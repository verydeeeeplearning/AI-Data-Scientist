"""Priority calculator for portfolio entry ordering.

Computes a priority score that the LLM uses as a *suggestion*
for task ordering.  The LLM is free to override this ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ds_agent.domain.portfolio.portfolio_entry import BusinessPriority, PortfolioEntry


class Clock(Protocol):
    def now(self) -> datetime: ...


@dataclass(frozen=True)
class PriorityScore:
    """Computed priority score for one portfolio entry."""

    entry_id: str
    raw_score: float
    sla_urgency: float
    business_weight: float
    age_factor: float


_BUSINESS_WEIGHTS: dict[BusinessPriority, float] = {
    BusinessPriority.P0: 4.0,
    BusinessPriority.P1: 3.0,
    BusinessPriority.P2: 2.0,
    BusinessPriority.P3: 1.0,
}


class PriorityCalculator:
    """Compute priority scores for portfolio entries.

    The resulting scores are informational — they appear in the
    system prompt context so the LLM can consider them when choosing
    which task to work on next.  The code does NOT enforce this ordering.
    """

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def score(self, entry: PortfolioEntry) -> PriorityScore:
        """Compute a priority score for one entry."""
        now = self._clock.now()

        business_weight = _BUSINESS_WEIGHTS.get(entry.business_priority, 2.0)

        sla_urgency = 0.0
        if entry.sla_deadline is not None:
            remaining = (entry.sla_deadline - now).total_seconds()
            if remaining <= 0:
                sla_urgency = 10.0  # overdue
            elif remaining < 3600:
                sla_urgency = 5.0  # < 1h
            elif remaining < 14400:
                sla_urgency = 3.0  # < 4h
            elif remaining < 86400:
                sla_urgency = 1.0  # < 1d

        age_seconds = (now - entry.created_at).total_seconds()
        age_factor = min(age_seconds / 86400, 5.0)  # cap at 5 days

        raw_score = business_weight * 2.0 + sla_urgency * 3.0 + age_factor * 0.5

        return PriorityScore(
            entry_id=entry.entry_id,
            raw_score=round(raw_score, 2),
            sla_urgency=round(sla_urgency, 2),
            business_weight=business_weight,
            age_factor=round(age_factor, 2),
        )

    def rank(self, entries: list[PortfolioEntry]) -> list[PriorityScore]:
        """Score and sort entries by priority (descending)."""
        scores = [self.score(e) for e in entries]
        return sorted(scores, key=lambda s: s.raw_score, reverse=True)
