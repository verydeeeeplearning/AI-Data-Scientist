from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from ds_agent.memory.semantic.infrastructure.sqlite_base import SemanticSqliteDatabase


def _db_path() -> Path:
    base_dir = Path("semantic_test_artifacts/migration")
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"{uuid.uuid4().hex}.db"


def test_semantic_migration_v6_applies_and_is_idempotent() -> None:
    db_path = _db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (5, datetime('now'))"
        )
        conn.commit()

    SemanticSqliteDatabase(db_path)
    SemanticSqliteDatabase(db_path)

    with sqlite3.connect(db_path) as conn:
        version = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            ).fetchall()
        }
    assert version == 7
    assert "semantic_metric" in tables
    assert "semantic_glossary" in tables
    assert "semantic_table_trust" in tables
    assert "semantic_verified_query" in tables
    assert "semantic_negative_knowledge" in tables
    assert "semantic_proposal" in tables
    # v7 introduces semantic snapshot manifest/row tables.
    assert "semantic_snapshot_manifest" in tables
    assert "semantic_snapshot_row" in tables

