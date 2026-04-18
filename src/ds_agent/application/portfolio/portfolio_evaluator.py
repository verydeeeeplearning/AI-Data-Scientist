"""Portfolio evaluator: assess resumable tasks and slot status.

The evaluator is an *information provider*, not a controller.
It evaluates wait conditions and reports which tasks are resumable,
which slots are available, and which SLA deadlines are at risk.
The LLM reads this information from the prompt context and decides
which tool to call (resume_task, pause_task, set_sla, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ds_agent.application.portfolio.priority_calculator import PriorityCalculator, PriorityScore
from ds_agent.application.portfolio.slot_manager import SlotManager
from ds_agent.application.portfolio.wait_condition_evaluator import (
    EvaluationResult,
    WaitConditionEvaluator,
)
from ds_agent.domain.interfaces.portfolio import PortfolioStore
from ds_agent.domain.portfolio.portfolio_entry import PortfolioEntry, PortfolioQuadrant


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Point-in-time portfolio state for prompt injection."""

    active_entries: list[PortfolioEntry] = field(default_factory=list)
    waiting_entries: list[PortfolioEntry] = field(default_factory=list)
    monitoring_entries: list[PortfolioEntry] = field(default_factory=list)
    candidate_entries: list[PortfolioEntry] = field(default_factory=list)
    resumable_conditions: list[EvaluationResult] = field(default_factory=list)
    priority_ranking: list[PriorityScore] = field(default_factory=list)
    active_slot_count: int = 0
    max_slots: int = 3
    available_slots: int = 3
    sla_at_risk_count: int = 0


class PortfolioEvaluator:
    """Evaluate the full portfolio and produce a snapshot.

    The snapshot is injected into the system prompt so the LLM can
    make informed decisions.  The evaluator does NOT perform any
    state transitions.
    """

    def __init__(
        self,
        store: PortfolioStore,
        slot_manager: SlotManager,
        condition_evaluator: WaitConditionEvaluator,
        priority_calculator: PriorityCalculator,
    ) -> None:
        self._store = store
        self._slots = slot_manager
        self._conditions = condition_evaluator
        self._priority = priority_calculator

    def evaluate(self) -> PortfolioSnapshot:
        """Produce a full portfolio snapshot."""
        active = self._store.list_entries(quadrant=PortfolioQuadrant.ACTIVE)
        waiting = self._store.list_entries(quadrant=PortfolioQuadrant.WAITING)
        monitoring = self._store.list_entries(quadrant=PortfolioQuadrant.MONITORING)
        candidates = self._store.list_entries(
            quadrant=PortfolioQuadrant.PLAYBOOK_CANDIDATE,
        )

        # Evaluate wait conditions for waiting entries.
        pending_conditions = self._store.list_pending_wait_conditions()
        condition_results = self._conditions.evaluate_all(pending_conditions)
        resumable = [r for r in condition_results if r.satisfied]

        # Priority ranking for active + waiting entries.
        ranking = self._priority.rank(active + waiting)

        # SLA risk detection.
        sla_at_risk = sum(
            1
            for score in ranking
            if score.sla_urgency >= 5.0
        )

        return PortfolioSnapshot(
            active_entries=active,
            waiting_entries=waiting,
            monitoring_entries=monitoring,
            candidate_entries=candidates,
            resumable_conditions=resumable,
            priority_ranking=ranking,
            active_slot_count=self._slots.active_count(),
            max_slots=self._slots.max_slots,
            available_slots=self._slots.available_slots(),
            sla_at_risk_count=sla_at_risk,
        )
