from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from ds_agent.memory.semantic.domain.org_context import (
    CalendarEvent,
    DecisionLogEntry,
    NegativeKnowledge,
    TeamOwnership,
)
from ds_agent.memory.semantic.infrastructure.sqlite_base import SemanticSqliteDatabase
from ds_agent.memory.semantic.infrastructure.sqlite_org_repo import SqliteOrgContextRepository


def _db() -> SemanticSqliteDatabase:
    base_dir = Path("semantic_test_artifacts/org")
    base_dir.mkdir(parents=True, exist_ok=True)
    return SemanticSqliteDatabase(base_dir / f"{uuid.uuid4().hex}.db")


def test_org_repo_round_trip() -> None:
    repo = SqliteOrgContextRepository(_db())
    repo.save_calendar_event(
        CalendarEvent(
            event_id="freeze.q2",
            type="freeze",
            name="Quarter close freeze",
            start_date=date(2026, 4, 10),
            end_date=date(2026, 4, 12),
            description="No schema changes",
            impact_hint="late refresh expected",
        )
    )
    repo.save_team(
        TeamOwnership(
            team="growth_team",
            contact="growth@corp.example",
            owned_metrics=["monthly_churn_rate"],
            owned_tables=["prod.growth.subscription"],
            approver_chain=["director", "vp"],
        )
    )
    repo.save_negative_knowledge(
        NegativeKnowledge(
            nk_id="nk-1",
            topic="monthly_churn_rate",
            wrong_approach="promo users 포함",
            why_wrong="biases churn downward",
            correct_approach="promo users 제외",
            recorded_at=datetime(2026, 4, 16, tzinfo=UTC),
            recorded_by="human",
            references=["DL-1"],
        )
    )
    repo.save_decision_log(
        DecisionLogEntry(
            decision_id="DL-1",
            date=date(2026, 4, 16),
            summary="Use growth churn definition",
            context="Quarterly KPI review",
            metrics_used=["monthly_churn_rate"],
            verified_query_ids=["vq_churn_001"],
            outcome="approved",
            rationale="Aligned with board reporting",
        )
    )

    events = repo.list_calendar_events(as_of=date(2026, 4, 11))
    assert [event.event_id for event in events] == ["freeze.q2"]

    team = repo.get_team("growth_team")
    assert team is not None
    assert team.owned_metrics == ["monthly_churn_rate"]

    knowledge = repo.list_negative_knowledge("monthly_churn_rate")
    assert [item.nk_id for item in knowledge] == ["nk-1"]

