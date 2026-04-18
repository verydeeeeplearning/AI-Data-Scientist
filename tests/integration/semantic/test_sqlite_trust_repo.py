from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

from ds_agent.memory.semantic.domain.trust import RefreshSLA, TableTrust, TrustGrade
from ds_agent.memory.semantic.infrastructure.sqlite_base import SemanticSqliteDatabase
from ds_agent.memory.semantic.infrastructure.sqlite_trust_repo import SqliteTableTrustRepository


def _db() -> SemanticSqliteDatabase:
    base_dir = Path("semantic_test_artifacts/trust")
    base_dir.mkdir(parents=True, exist_ok=True)
    return SemanticSqliteDatabase(base_dir / f"{uuid.uuid4().hex}.db")


def test_trust_repo_round_trip_and_bulk_get() -> None:
    repo = SqliteTableTrustRepository(_db())
    table = TableTrust(
        fqtn="prod.growth.subscription",
        grade=TrustGrade.GOLD,
        owner="growth_team",
        description="subscription fact",
        refresh=RefreshSLA(cadence="daily", max_staleness_minutes=1440),
        grade_rationale="audited",
        last_audited=date(2026, 4, 1),
    )
    repo.save(table)

    restored = repo.get(table.fqtn)
    assert restored is not None
    assert restored.grade is TrustGrade.GOLD

    bulk = repo.bulk_get([table.fqtn, "missing.table"])
    assert [item.fqtn for item in bulk] == [table.fqtn]

