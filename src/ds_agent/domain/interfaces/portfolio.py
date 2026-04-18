"""Persistence contract for the async portfolio manager."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ds_agent.domain.portfolio.playbook_candidate import PlaybookCandidate
from ds_agent.domain.portfolio.portfolio_checkpoint import PortfolioCheckpoint
from ds_agent.domain.portfolio.portfolio_entry import PortfolioEntry, PortfolioTransition
from ds_agent.domain.portfolio.wait_condition import WaitCondition


@runtime_checkable
class PortfolioStore(Protocol):
    """Storage contract for portfolio entries and related state."""

    # ── Portfolio entries ─────────────────────────────────────────────

    def create_entry(self, entry: PortfolioEntry) -> None: ...

    def get_entry(self, entry_id: str) -> PortfolioEntry | None: ...

    def get_entry_by_task(self, task_contract_id: str) -> PortfolioEntry | None: ...

    def list_entries(
        self,
        *,
        quadrant: str | None = None,
        limit: int = 50,
    ) -> list[PortfolioEntry]: ...

    def save_entry(self, entry: PortfolioEntry) -> None: ...

    # ── Transitions ──────────────────────────────────────────────────

    def record_transition(
        self,
        entry_id: str,
        transition: PortfolioTransition,
    ) -> None: ...

    def list_transitions(
        self,
        entry_id: str,
        *,
        limit: int = 50,
    ) -> list[PortfolioTransition]: ...

    # ── Wait conditions ──────────────────────────────────────────────

    def save_wait_condition(self, condition: WaitCondition) -> None: ...

    def get_wait_condition(self, condition_id: str) -> WaitCondition | None: ...

    def list_pending_wait_conditions(self, *, limit: int = 50) -> list[WaitCondition]: ...

    # ── Checkpoints ──────────────────────────────────────────────────

    def save_checkpoint(self, checkpoint: PortfolioCheckpoint) -> None: ...

    def get_checkpoint(self, entry_id: str) -> PortfolioCheckpoint | None: ...

    # ── Playbook candidates ──────────────────────────────────────────

    def save_playbook_candidate(self, candidate: PlaybookCandidate) -> None: ...

    def list_playbook_candidates(self, *, limit: int = 20) -> list[PlaybookCandidate]: ...
