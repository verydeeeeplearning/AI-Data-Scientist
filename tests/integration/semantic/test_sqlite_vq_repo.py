from __future__ import annotations

import sqlite3
import uuid
from datetime import date
from pathlib import Path

from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery
from ds_agent.memory.semantic.infrastructure.sqlite_base import SemanticSqliteDatabase
from ds_agent.memory.semantic.infrastructure.sqlite_vq_repo import SqliteVerifiedQueryRepository


def _db_path() -> Path:
    base_dir = Path("semantic_test_artifacts/vq")
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"{uuid.uuid4().hex}.db"


def test_vq_repo_round_trip_and_audit_append() -> None:
    db_path = _db_path()
    db = SemanticSqliteDatabase(db_path)
    repo = SqliteVerifiedQueryRepository(db)
    query = VerifiedQuery(
        vq_id="vq_churn_001",
        metric_id="monthly_churn_rate",
        dialect="postgres",
        description="Monthly churn",
        sql_template="SELECT {{start_date}}",
        parameters=[{"name": "start_date", "type": "date", "description": "inclusive start"}],
        referenced_tables=["prod.growth.subscription"],
        verified_by="reviewer",
        last_verified=date(2026, 4, 15),
        verification_evidence="Dashboard parity",
    )
    repo.save(query)
    repo.append_audit(
        query.vq_id,
        verified_by="reviewer",
        verification_evidence="Dashboard parity",
        verified_at=date(2026, 4, 15),
    )

    restored = repo.get(query.vq_id)
    assert restored is not None
    assert restored.vq_id == query.vq_id

    matches = repo.find_by_metric("monthly_churn_rate", dialect="postgres")
    assert [item.vq_id for item in matches] == [query.vq_id]

    with sqlite3.connect(db_path) as conn:
        audit_count = conn.execute(
            "SELECT COUNT(*) FROM semantic_verified_query_audit WHERE vq_id = ?",
            (query.vq_id,),
        ).fetchone()[0]
    assert audit_count == 1

