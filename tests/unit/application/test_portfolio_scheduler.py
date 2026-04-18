"""Tests for portfolio evaluator, slot manager, and wait condition evaluator.

Key principle: the evaluator only *reports* — it does NOT perform transitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from ds_agent.application.portfolio.portfolio_evaluator import (
    PortfolioEvaluator,
    PortfolioSnapshot,
)
from ds_agent.application.portfolio.priority_calculator import PriorityCalculator
from ds_agent.application.portfolio.slot_manager import SlotManager
from ds_agent.application.portfolio.wait_condition_evaluator import (
    WaitConditionEvaluator,
)
from ds_agent.domain.portfolio.portfolio_entry import (
    BusinessPriority,
    PortfolioEntry,
    PortfolioQuadrant,
)
from ds_agent.domain.portfolio.wait_condition import WaitCondition, WaitConditionKind

NOW = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)


@dataclass
class _MockClock:
    now_value: datetime = NOW

    def now(self) -> datetime:
        return self.now_value


def _make_store_mock(
    active: list[PortfolioEntry] | None = None,
    waiting: list[PortfolioEntry] | None = None,
    pending_conditions: list[WaitCondition] | None = None,
) -> MagicMock:
    store = MagicMock()

    def list_entries(*, quadrant: str | None = None, limit: int = 50):
        if quadrant == PortfolioQuadrant.ACTIVE:
            return active or []
        if quadrant == PortfolioQuadrant.WAITING:
            return waiting or []
        if quadrant == PortfolioQuadrant.MONITORING:
            return []
        if quadrant == PortfolioQuadrant.PLAYBOOK_CANDIDATE:
            return []
        return (active or []) + (waiting or [])

    store.list_entries = list_entries
    store.list_pending_wait_conditions.return_value = pending_conditions or []
    return store


def _active_entry(entry_id: str = "PE-A1", priority: BusinessPriority = BusinessPriority.P1):
    return PortfolioEntry(
        entry_id=entry_id,
        task_contract_id=f"TC-{entry_id}",
        quadrant=PortfolioQuadrant.ACTIVE,
        business_priority=priority,
        parent_run_id=f"run-{entry_id}",
        created_at=NOW - timedelta(hours=2),
        updated_at=NOW,
        last_transition_at=NOW,
    )


class TestWaitConditionEvaluator:
    def test_timer_satisfied(self) -> None:
        clock = _MockClock(NOW + timedelta(hours=2))
        evaluator = WaitConditionEvaluator(clock)
        wc = WaitCondition.create(
            condition_id="WC-T1",
            kind=WaitConditionKind.TIMER,
            spec={"resume_at": NOW.isoformat()},
            now=NOW,
        )
        result = evaluator.evaluate(wc)
        assert result.satisfied is True
        assert "expired" in result.reason

    def test_timer_not_yet(self) -> None:
        clock = _MockClock(NOW)
        evaluator = WaitConditionEvaluator(clock)
        future = (NOW + timedelta(hours=1)).isoformat()
        wc = WaitCondition.create(
            condition_id="WC-T2",
            kind=WaitConditionKind.TIMER,
            spec={"resume_at": future},
            now=NOW,
        )
        result = evaluator.evaluate(wc)
        assert result.satisfied is False
        assert "remaining" in result.reason

    def test_timer_missing_spec(self) -> None:
        evaluator = WaitConditionEvaluator(_MockClock())
        wc = WaitCondition.create(
            condition_id="WC-T3",
            kind=WaitConditionKind.TIMER,
            spec={},
            now=NOW,
        )
        result = evaluator.evaluate(wc)
        assert result.satisfied is False
        assert "missing" in result.reason

    def test_evaluate_all_batch(self) -> None:
        clock = _MockClock(NOW + timedelta(hours=2))
        evaluator = WaitConditionEvaluator(clock)
        conditions = [
            WaitCondition.create(
                condition_id="WC-B1",
                kind=WaitConditionKind.TIMER,
                spec={"resume_at": NOW.isoformat()},
                now=NOW,
            ),
            WaitCondition.create(
                condition_id="WC-B2",
                kind=WaitConditionKind.APPROVAL,
                spec={"approval_id": "apr_123"},
                now=NOW,
            ),
        ]
        results = evaluator.evaluate_all(conditions)
        assert len(results) == 2
        assert results[0].satisfied is True
        assert results[1].satisfied is False


class TestSlotManager:
    def test_available_when_empty(self) -> None:
        store = _make_store_mock()
        mgr = SlotManager(store)
        assert mgr.can_acquire()
        assert mgr.available_slots() == mgr.max_slots

    def test_full_slots_refuse(self) -> None:
        entries = [_active_entry(f"PE-{i}") for i in range(3)]
        store = _make_store_mock(active=entries)
        mgr = SlotManager(store)
        refusal = mgr.acquire_or_refuse()
        assert refusal is not None
        assert "occupied" in refusal

    def test_partial_slots_allow(self) -> None:
        entries = [_active_entry("PE-1")]
        store = _make_store_mock(active=entries)
        mgr = SlotManager(store)
        assert mgr.can_acquire()
        assert mgr.acquire_or_refuse() is None


class TestPriorityCalculator:
    def test_p0_scores_higher_than_p3(self) -> None:
        calc = PriorityCalculator(_MockClock())
        p0 = _active_entry("PE-P0", BusinessPriority.P0)
        p3 = _active_entry("PE-P3", BusinessPriority.P3)
        scores = calc.rank([p3, p0])
        assert scores[0].entry_id == "PE-P0"
        assert scores[0].raw_score > scores[1].raw_score

    def test_sla_urgency_for_overdue(self) -> None:
        calc = PriorityCalculator(_MockClock())
        entry = PortfolioEntry(
            entry_id="PE-SLA",
            task_contract_id="TC-SLA",
            quadrant=PortfolioQuadrant.ACTIVE,
            business_priority=BusinessPriority.P2,
            parent_run_id="run-sla",
            sla_deadline=NOW - timedelta(hours=1),
            created_at=NOW - timedelta(days=1),
            updated_at=NOW,
            last_transition_at=NOW,
        )
        score = calc.score(entry)
        assert score.sla_urgency == 10.0


class TestPortfolioEvaluator:
    def test_evaluate_returns_snapshot(self) -> None:
        active = [_active_entry("PE-A1")]
        waiting_entry = PortfolioEntry(
            entry_id="PE-W1",
            task_contract_id="TC-W1",
            quadrant=PortfolioQuadrant.WAITING,
            wait_condition_id="WC-T1",
            created_at=NOW,
            updated_at=NOW,
            last_transition_at=NOW,
        )
        timer_cond = WaitCondition.create(
            condition_id="WC-T1",
            kind=WaitConditionKind.TIMER,
            spec={"resume_at": (NOW - timedelta(hours=1)).isoformat()},
            now=NOW - timedelta(hours=2),
        )
        store = _make_store_mock(
            active=active,
            waiting=[waiting_entry],
            pending_conditions=[timer_cond],
        )
        clock = _MockClock(NOW)
        evaluator = PortfolioEvaluator(
            store=store,
            slot_manager=SlotManager(store),
            condition_evaluator=WaitConditionEvaluator(clock),
            priority_calculator=PriorityCalculator(clock),
        )
        snapshot = evaluator.evaluate()
        assert isinstance(snapshot, PortfolioSnapshot)
        assert len(snapshot.active_entries) == 1
        assert len(snapshot.waiting_entries) == 1
        assert len(snapshot.resumable_conditions) == 1
        assert snapshot.active_slot_count == 1
        assert snapshot.available_slots >= 1

    def test_evaluator_does_not_transition(self) -> None:
        """The evaluator must NOT call save_entry or any mutation method."""
        store = _make_store_mock(active=[], waiting=[])
        clock = _MockClock(NOW)
        evaluator = PortfolioEvaluator(
            store=store,
            slot_manager=SlotManager(store),
            condition_evaluator=WaitConditionEvaluator(clock),
            priority_calculator=PriorityCalculator(clock),
        )
        evaluator.evaluate()
        store.save_entry.assert_not_called()
        store.create_entry.assert_not_called()
