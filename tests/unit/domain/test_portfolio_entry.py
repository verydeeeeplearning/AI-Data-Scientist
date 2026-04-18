"""Tests for portfolio domain entities and invariants."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ds_agent.domain.portfolio.portfolio_entry import (
    BusinessPriority,
    PortfolioEntry,
    PortfolioQuadrant,
    PortfolioTransition,
    TerminalQuadrant,
    can_transition,
)
from ds_agent.domain.portfolio.wait_condition import (
    WaitCondition,
    WaitConditionKind,
)

NOW = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)


def _make_active_entry(entry_id: str = "PE-001") -> PortfolioEntry:
    return PortfolioEntry(
        entry_id=entry_id,
        task_contract_id="TC-2026-001",
        quadrant=PortfolioQuadrant.ACTIVE,
        business_priority=BusinessPriority.P1,
        parent_run_id="run-001",
        created_at=NOW,
        updated_at=NOW,
        last_transition_at=NOW,
    )


def _make_waiting_entry(entry_id: str = "PE-002") -> PortfolioEntry:
    return PortfolioEntry(
        entry_id=entry_id,
        task_contract_id="TC-2026-002",
        quadrant=PortfolioQuadrant.WAITING,
        business_priority=BusinessPriority.P2,
        wait_condition_id="WC-001",
        created_at=NOW,
        updated_at=NOW,
        last_transition_at=NOW,
    )


class TestPortfolioEntryInvariants:
    def test_active_requires_run_id(self) -> None:
        with pytest.raises(ValueError, match="parent_run_id"):
            PortfolioEntry(
                entry_id="PE-X",
                task_contract_id="TC-X",
                quadrant=PortfolioQuadrant.ACTIVE,
                created_at=NOW,
                updated_at=NOW,
                last_transition_at=NOW,
            )

    def test_waiting_requires_condition_id(self) -> None:
        with pytest.raises(ValueError, match="wait_condition_id"):
            PortfolioEntry(
                entry_id="PE-X",
                task_contract_id="TC-X",
                quadrant=PortfolioQuadrant.WAITING,
                created_at=NOW,
                updated_at=NOW,
                last_transition_at=NOW,
            )

    def test_waiting_rejects_run_id(self) -> None:
        with pytest.raises(ValueError, match="must not have parent_run_id"):
            PortfolioEntry(
                entry_id="PE-X",
                task_contract_id="TC-X",
                quadrant=PortfolioQuadrant.WAITING,
                wait_condition_id="WC-001",
                parent_run_id="run-001",
                created_at=NOW,
                updated_at=NOW,
                last_transition_at=NOW,
            )

    def test_monitoring_requires_metric_ref(self) -> None:
        with pytest.raises(ValueError, match="monitoring_metric_ref"):
            PortfolioEntry(
                entry_id="PE-X",
                task_contract_id="TC-X",
                quadrant=PortfolioQuadrant.MONITORING,
                created_at=NOW,
                updated_at=NOW,
                last_transition_at=NOW,
            )

    def test_playbook_candidate_requires_ref(self) -> None:
        with pytest.raises(ValueError, match="playbook_candidate_ref"):
            PortfolioEntry(
                entry_id="PE-X",
                task_contract_id="TC-X",
                quadrant=PortfolioQuadrant.PLAYBOOK_CANDIDATE,
                created_at=NOW,
                updated_at=NOW,
                last_transition_at=NOW,
            )

    def test_valid_active_entry(self) -> None:
        entry = _make_active_entry()
        assert entry.quadrant == PortfolioQuadrant.ACTIVE
        assert entry.parent_run_id == "run-001"


class TestPortfolioTransitions:
    def test_active_to_waiting(self) -> None:
        entry = _make_active_entry()
        later = NOW + timedelta(hours=1)
        waiting = entry.transition_to(
            PortfolioQuadrant.WAITING,
            reason="data not fresh",
            actor="llm",
            now=later,
            wait_condition_id="WC-new",
        )
        assert waiting.quadrant == PortfolioQuadrant.WAITING
        assert waiting.wait_condition_id == "WC-new"
        assert waiting.parent_run_id is None

    def test_active_to_completed(self) -> None:
        entry = _make_active_entry()
        completed = entry.transition_to(
            TerminalQuadrant.COMPLETED,
            reason="analysis done",
            actor="llm",
            now=NOW + timedelta(hours=2),
        )
        assert completed.quadrant == TerminalQuadrant.COMPLETED

    def test_waiting_to_active(self) -> None:
        entry = _make_waiting_entry()
        resumed = entry.transition_to(
            PortfolioQuadrant.ACTIVE,
            reason="condition satisfied",
            actor="llm",
            now=NOW + timedelta(hours=1),
            run_id="run-002",
        )
        assert resumed.quadrant == PortfolioQuadrant.ACTIVE
        assert resumed.parent_run_id == "run-002"

    def test_completed_cannot_go_active(self) -> None:
        assert not can_transition(TerminalQuadrant.COMPLETED, PortfolioQuadrant.ACTIVE)

    def test_monitoring_cannot_go_waiting(self) -> None:
        assert not can_transition(PortfolioQuadrant.MONITORING, PortfolioQuadrant.WAITING)

    def test_forbidden_transition_raises(self) -> None:
        entry = _make_waiting_entry()
        with pytest.raises(ValueError, match="not allowed"):
            entry.transition_to(
                TerminalQuadrant.COMPLETED,
                reason="invalid",
                now=NOW,
            )


class TestBusinessPriority:
    def test_sla_hours(self) -> None:
        assert BusinessPriority.P0.sla_hours == 4
        assert BusinessPriority.P1.sla_hours == 24
        assert BusinessPriority.P2.sla_hours == 72
        assert BusinessPriority.P3.sla_hours is None


class TestPortfolioTransitionModel:
    def test_transition_record(self) -> None:
        t = PortfolioTransition(
            from_quadrant=PortfolioQuadrant.ACTIVE,
            to_quadrant=PortfolioQuadrant.WAITING,
            reason="paused for data",
            actor="llm",
            at=NOW,
        )
        assert t.actor == "llm"
        assert t.reason == "paused for data"


class TestWaitCondition:
    def test_timer_creation(self) -> None:
        wc = WaitCondition.create(
            condition_id="WC-001",
            kind=WaitConditionKind.TIMER,
            spec={"resume_at": "2026-04-17T09:00:00+00:00"},
            now=NOW,
        )
        assert wc.poll_interval_s == 60
        assert not wc.is_satisfied

    def test_satisfied_check(self) -> None:
        wc = WaitCondition(
            condition_id="WC-002",
            kind=WaitConditionKind.TIMER,
            spec={},
            created_at=NOW,
            last_checked_at=NOW,
            last_check_result="satisfied",
        )
        assert wc.is_satisfied

    def test_overdue(self) -> None:
        deadline = NOW - timedelta(hours=1)
        wc = WaitCondition(
            condition_id="WC-003",
            kind=WaitConditionKind.DATA_FRESHNESS,
            spec={},
            created_at=NOW - timedelta(hours=2),
            deadline=deadline,
            last_checked_at=NOW,
            last_check_result="pending",
        )
        assert wc.is_overdue

    def test_with_check_result(self) -> None:
        wc = WaitCondition.create(
            condition_id="WC-004",
            kind=WaitConditionKind.APPROVAL,
            spec={"approval_id": "apr_123"},
            now=NOW,
        )
        updated = wc.with_check_result("satisfied", NOW + timedelta(minutes=5))
        assert updated.is_satisfied
        assert updated.last_checked_at == NOW + timedelta(minutes=5)
