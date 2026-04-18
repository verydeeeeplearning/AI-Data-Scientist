"""Integration tests for SqlitePortfolioStore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ds_agent.domain.portfolio.playbook_candidate import PlaybookCandidate
from ds_agent.domain.portfolio.portfolio_checkpoint import PortfolioCheckpoint
from ds_agent.domain.portfolio.portfolio_entry import (
    BusinessPriority,
    PortfolioEntry,
    PortfolioQuadrant,
    PortfolioTransition,
)
from ds_agent.domain.portfolio.wait_condition import WaitCondition, WaitConditionKind
from ds_agent.infrastructure.persistence.portfolio_store import SqlitePortfolioStore

NOW = datetime(2026, 4, 16, 10, 0, tzinfo=UTC)


@pytest.fixture()
def store(tmp_path: Path) -> SqlitePortfolioStore:
    return SqlitePortfolioStore(tmp_path / "test_portfolio.db")


def _active_entry(entry_id: str = "PE-001") -> PortfolioEntry:
    return PortfolioEntry(
        entry_id=entry_id,
        task_contract_id=f"TC-{entry_id}",
        quadrant=PortfolioQuadrant.ACTIVE,
        business_priority=BusinessPriority.P1,
        parent_run_id="run-001",
        created_at=NOW,
        updated_at=NOW,
        last_transition_at=NOW,
        tags=["churn", "weekly"],
    )


class TestPortfolioEntryCRUD:
    def test_create_and_get(self, store: SqlitePortfolioStore) -> None:
        entry = _active_entry()
        store.create_entry(entry)
        loaded = store.get_entry("PE-001")
        assert loaded is not None
        assert loaded.entry_id == "PE-001"
        assert loaded.quadrant == PortfolioQuadrant.ACTIVE
        assert loaded.business_priority == BusinessPriority.P1
        assert loaded.tags == ["churn", "weekly"]

    def test_get_nonexistent_returns_none(self, store: SqlitePortfolioStore) -> None:
        assert store.get_entry("PE-NOPE") is None

    def test_get_by_task(self, store: SqlitePortfolioStore) -> None:
        entry = _active_entry()
        store.create_entry(entry)
        loaded = store.get_entry_by_task("TC-PE-001")
        assert loaded is not None
        assert loaded.entry_id == "PE-001"

    def test_list_by_quadrant(self, store: SqlitePortfolioStore) -> None:
        store.create_entry(_active_entry("PE-A"))
        store.create_entry(
            PortfolioEntry(
                entry_id="PE-W",
                task_contract_id="TC-PE-W",
                quadrant=PortfolioQuadrant.WAITING,
                wait_condition_id="WC-001",
                created_at=NOW,
                updated_at=NOW,
                last_transition_at=NOW,
            ),
        )
        active = store.list_entries(quadrant=PortfolioQuadrant.ACTIVE)
        assert len(active) == 1
        assert active[0].entry_id == "PE-A"

        waiting = store.list_entries(quadrant=PortfolioQuadrant.WAITING)
        assert len(waiting) == 1

    def test_save_entry_updates(self, store: SqlitePortfolioStore) -> None:
        entry = _active_entry()
        store.create_entry(entry)
        updated = entry.model_copy(
            update={
                "business_priority": BusinessPriority.P0,
                "updated_at": NOW + timedelta(hours=1),
            },
        )
        store.save_entry(updated)
        loaded = store.get_entry("PE-001")
        assert loaded is not None
        assert loaded.business_priority == BusinessPriority.P0


class TestTransitions:
    def test_record_and_list(self, store: SqlitePortfolioStore) -> None:
        store.create_entry(_active_entry())
        t = PortfolioTransition(
            from_quadrant=None,
            to_quadrant=PortfolioQuadrant.ACTIVE,
            reason="initial",
            actor="system",
            at=NOW,
        )
        store.record_transition("PE-001", t)
        transitions = store.list_transitions("PE-001")
        assert len(transitions) == 1
        assert transitions[0].to_quadrant == PortfolioQuadrant.ACTIVE


class TestWaitConditions:
    def test_save_and_get(self, store: SqlitePortfolioStore) -> None:
        wc = WaitCondition.create(
            condition_id="WC-001",
            kind=WaitConditionKind.TIMER,
            spec={"resume_at": "2026-04-17T09:00:00+00:00"},
            now=NOW,
        )
        store.save_wait_condition(wc)
        loaded = store.get_wait_condition("WC-001")
        assert loaded is not None
        assert loaded.kind == WaitConditionKind.TIMER
        assert loaded.poll_interval_s == 60

    def test_list_pending(self, store: SqlitePortfolioStore) -> None:
        wc1 = WaitCondition.create(
            condition_id="WC-P1",
            kind=WaitConditionKind.TIMER,
            spec={},
            now=NOW,
        )
        wc2 = WaitCondition(
            condition_id="WC-DONE",
            kind=WaitConditionKind.TIMER,
            spec={},
            created_at=NOW,
            last_check_result="satisfied",
        )
        store.save_wait_condition(wc1)
        store.save_wait_condition(wc2)
        pending = store.list_pending_wait_conditions()
        assert len(pending) == 1
        assert pending[0].condition_id == "WC-P1"


class TestCheckpoints:
    def test_save_and_get(self, store: SqlitePortfolioStore) -> None:
        store.create_entry(_active_entry())
        cp = PortfolioCheckpoint(
            checkpoint_id="CP-001",
            entry_id="PE-001",
            run_id="run-001",
            step_index=3,
            state_json={"model": "xgboost", "features": 42},
            created_at=NOW,
        )
        store.save_checkpoint(cp)
        loaded = store.get_checkpoint("PE-001")
        assert loaded is not None
        assert loaded.step_index == 3
        assert loaded.state_json["model"] == "xgboost"


class TestPlaybookCandidates:
    def test_save_and_list(self, store: SqlitePortfolioStore) -> None:
        store.create_entry(_active_entry())
        pc = PlaybookCandidate(
            candidate_id="PB-001",
            entry_id="PE-001",
            pattern_signature="churn_analysis_v1",
            description="Weekly churn triage pattern",
            confidence=0.85,
            created_at=NOW,
        )
        store.save_playbook_candidate(pc)
        candidates = store.list_playbook_candidates()
        assert len(candidates) == 1
        assert candidates[0].pattern_signature == "churn_analysis_v1"
