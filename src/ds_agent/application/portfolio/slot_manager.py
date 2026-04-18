"""Slot manager: hard constraint for concurrent active tasks."""

from __future__ import annotations

import os

from ds_agent.domain.interfaces.portfolio import PortfolioStore
from ds_agent.domain.portfolio.portfolio_entry import PortfolioQuadrant

_DEFAULT_MAX_ACTIVE_SLOTS = 3


def _max_active_slots() -> int:
    raw = os.environ.get("DS_AGENT_MAX_ACTIVE_SLOTS", "")
    if raw.isdigit():
        return max(int(raw), 1)
    return _DEFAULT_MAX_ACTIVE_SLOTS


class SlotManager:
    """Enforce max_active_slots hard constraint.

    This is a hard constraint — code enforces it.  The LLM cannot
    override slot limits.  When a slot is unavailable, the
    ``resume_task`` tool returns a refusal response and the LLM
    decides how to proceed.
    """

    def __init__(self, store: PortfolioStore) -> None:
        self._store = store

    @property
    def max_slots(self) -> int:
        return _max_active_slots()

    def active_count(self) -> int:
        return len(
            self._store.list_entries(quadrant=PortfolioQuadrant.ACTIVE),
        )

    def available_slots(self) -> int:
        return max(0, self.max_slots - self.active_count())

    def can_acquire(self) -> bool:
        return self.available_slots() > 0

    def acquire_or_refuse(self) -> str | None:
        """Try to acquire a slot.  Return None on success, or a refusal message."""
        if self.can_acquire():
            return None
        return (
            f"All {self.max_slots} active slots are occupied. "
            f"Pause or complete an active task before resuming another."
        )
