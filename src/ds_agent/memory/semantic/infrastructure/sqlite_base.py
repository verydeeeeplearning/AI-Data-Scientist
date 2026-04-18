"""Shared SQLite primitives for semantic memory repositories."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

_MIGRATION_V6_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS semantic_metric (
    metric_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    owner TEXT NOT NULL,
    owner_contact TEXT,
    definition TEXT NOT NULL,
    synonyms_json TEXT NOT NULL,
    synonyms_text TEXT NOT NULL,
    grain TEXT NOT NULL,
    unit TEXT NOT NULL,
    direction TEXT NOT NULL,
    typical_range_min REAL,
    typical_range_max REAL,
    calculation_json TEXT NOT NULL,
    related_metrics_json TEXT NOT NULL,
    approved_by_json TEXT NOT NULL,
    caveats_json TEXT NOT NULL,
    verified_query_ids_json TEXT NOT NULL,
    version INTEGER NOT NULL,
    last_reviewed TEXT
);
CREATE TABLE IF NOT EXISTS semantic_metric_synonym (
    metric_id TEXT NOT NULL REFERENCES semantic_metric(metric_id) ON DELETE CASCADE,
    synonym TEXT NOT NULL,
    PRIMARY KEY (metric_id, synonym)
);
CREATE INDEX IF NOT EXISTS idx_metric_synonym ON semantic_metric_synonym(synonym);
CREATE VIRTUAL TABLE IF NOT EXISTS semantic_metric_fts USING fts5(
    metric_id UNINDEXED,
    display_name,
    definition,
    synonyms
);

CREATE TABLE IF NOT EXISTS semantic_glossary (
    term_id TEXT PRIMARY KEY,
    canonical_form TEXT NOT NULL,
    definition TEXT NOT NULL,
    synonyms_json TEXT NOT NULL,
    abbreviations_json TEXT NOT NULL,
    translations_json TEXT NOT NULL,
    linked_metric_ids_json TEXT NOT NULL,
    category TEXT NOT NULL,
    owner TEXT,
    variants_text TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS semantic_glossary_fts USING fts5(
    term_id UNINDEXED,
    canonical_form,
    definition,
    variants
);

CREATE TABLE IF NOT EXISTS semantic_table_trust (
    fqtn TEXT PRIMARY KEY,
    grade TEXT NOT NULL,
    owner TEXT NOT NULL,
    description TEXT NOT NULL,
    refresh_json TEXT NOT NULL,
    columns_json TEXT NOT NULL,
    approved_joins_json TEXT NOT NULL,
    grade_rationale TEXT NOT NULL,
    last_audited TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_table_trust_grade ON semantic_table_trust(grade);

CREATE TABLE IF NOT EXISTS semantic_verified_query (
    vq_id TEXT PRIMARY KEY,
    metric_id TEXT,
    dialect TEXT NOT NULL,
    description TEXT NOT NULL,
    sql_template TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    referenced_tables_json TEXT NOT NULL,
    verified_by TEXT NOT NULL,
    last_verified TEXT NOT NULL,
    verification_evidence TEXT NOT NULL,
    failure_modes_json TEXT NOT NULL,
    tags_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vq_metric ON semantic_verified_query(metric_id, dialect);

CREATE TABLE IF NOT EXISTS semantic_verified_query_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vq_id TEXT NOT NULL REFERENCES semantic_verified_query(vq_id) ON DELETE CASCADE,
    verified_by TEXT NOT NULL,
    verification_evidence TEXT NOT NULL,
    verified_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS semantic_calendar_event (
    event_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    description TEXT NOT NULL,
    impact_hint TEXT
);
CREATE INDEX IF NOT EXISTS idx_calendar_range ON semantic_calendar_event(start_date, end_date);

CREATE TABLE IF NOT EXISTS semantic_team_ownership (
    team TEXT PRIMARY KEY,
    contact TEXT NOT NULL,
    owned_metrics_json TEXT NOT NULL,
    owned_tables_json TEXT NOT NULL,
    approver_chain_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS semantic_decision_log (
    decision_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    summary TEXT NOT NULL,
    context TEXT NOT NULL,
    metrics_used_json TEXT NOT NULL,
    verified_query_ids_json TEXT NOT NULL,
    outcome TEXT NOT NULL,
    rationale TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS semantic_negative_knowledge (
    nk_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    wrong_approach TEXT NOT NULL,
    why_wrong TEXT NOT NULL,
    correct_approach TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    recorded_by TEXT NOT NULL,
    references_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nk_topic ON semantic_negative_knowledge(topic);

CREATE TABLE IF NOT EXISTS semantic_proposal (
    proposal_id TEXT PRIMARY KEY,
    proposal_type TEXT NOT NULL,
    status TEXT NOT NULL,
    source_run_id TEXT,
    source_session_id TEXT,
    source_tool_name TEXT,
    target_id TEXT,
    summary TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    risk TEXT NOT NULL,
    proposed_by TEXT NOT NULL,
    auto_apply_eligible INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_proposal_status ON semantic_proposal(status, created_at);
CREATE INDEX IF NOT EXISTS idx_proposal_target ON semantic_proposal(target_id);

CREATE TABLE IF NOT EXISTS semantic_proposal_evidence (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL REFERENCES semantic_proposal(proposal_id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL,
    evidence_ref TEXT NOT NULL,
    note TEXT
);

CREATE TRIGGER IF NOT EXISTS trg_metric_fts_insert AFTER INSERT ON semantic_metric
BEGIN
    INSERT INTO semantic_metric_fts(rowid, metric_id, display_name, definition, synonyms)
    VALUES (NEW.rowid, NEW.metric_id, NEW.display_name, NEW.definition, NEW.synonyms_text);
END;
CREATE TRIGGER IF NOT EXISTS trg_metric_fts_delete AFTER DELETE ON semantic_metric
BEGIN
    DELETE FROM semantic_metric_fts WHERE rowid = OLD.rowid;
END;
CREATE TRIGGER IF NOT EXISTS trg_metric_fts_update AFTER UPDATE ON semantic_metric
BEGIN
    DELETE FROM semantic_metric_fts WHERE rowid = OLD.rowid;
    INSERT INTO semantic_metric_fts(rowid, metric_id, display_name, definition, synonyms)
    VALUES (NEW.rowid, NEW.metric_id, NEW.display_name, NEW.definition, NEW.synonyms_text);
END;

CREATE TRIGGER IF NOT EXISTS trg_glossary_fts_insert AFTER INSERT ON semantic_glossary
BEGIN
    INSERT INTO semantic_glossary_fts(rowid, term_id, canonical_form, definition, variants)
    VALUES (NEW.rowid, NEW.term_id, NEW.canonical_form, NEW.definition, NEW.variants_text);
END;
CREATE TRIGGER IF NOT EXISTS trg_glossary_fts_delete AFTER DELETE ON semantic_glossary
BEGIN
    DELETE FROM semantic_glossary_fts WHERE rowid = OLD.rowid;
END;
CREATE TRIGGER IF NOT EXISTS trg_glossary_fts_update AFTER UPDATE ON semantic_glossary
BEGIN
    DELETE FROM semantic_glossary_fts WHERE rowid = OLD.rowid;
    INSERT INTO semantic_glossary_fts(rowid, term_id, canonical_form, definition, variants)
    VALUES (NEW.rowid, NEW.term_id, NEW.canonical_form, NEW.definition, NEW.variants_text);
END;

INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (6, datetime('now'));
"""

_MIGRATION_V7_SQL = """
CREATE TABLE IF NOT EXISTS semantic_snapshot_manifest (
    snapshot_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    note TEXT,
    table_counts_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_semantic_snapshot_created
ON semantic_snapshot_manifest(created_at DESC);

CREATE TABLE IF NOT EXISTS semantic_snapshot_row (
    snapshot_id TEXT NOT NULL
        REFERENCES semantic_snapshot_manifest(snapshot_id) ON DELETE CASCADE,
    table_name TEXT NOT NULL,
    row_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, table_name, row_key)
);
CREATE INDEX IF NOT EXISTS idx_semantic_snapshot_row_table
ON semantic_snapshot_row(snapshot_id, table_name);

DROP TRIGGER IF EXISTS trg_metric_fts_insert;
DROP TRIGGER IF EXISTS trg_metric_fts_delete;
DROP TRIGGER IF EXISTS trg_metric_fts_update;
CREATE TRIGGER IF NOT EXISTS trg_metric_fts_insert AFTER INSERT ON semantic_metric
BEGIN
    INSERT INTO semantic_metric_fts(rowid, metric_id, display_name, definition, synonyms)
    VALUES (NEW.rowid, NEW.metric_id, NEW.display_name, NEW.definition, NEW.synonyms_text);
END;
CREATE TRIGGER IF NOT EXISTS trg_metric_fts_delete AFTER DELETE ON semantic_metric
BEGIN
    DELETE FROM semantic_metric_fts WHERE rowid = OLD.rowid;
END;
CREATE TRIGGER IF NOT EXISTS trg_metric_fts_update AFTER UPDATE ON semantic_metric
BEGIN
    DELETE FROM semantic_metric_fts WHERE rowid = OLD.rowid;
    INSERT INTO semantic_metric_fts(rowid, metric_id, display_name, definition, synonyms)
    VALUES (NEW.rowid, NEW.metric_id, NEW.display_name, NEW.definition, NEW.synonyms_text);
END;

DROP TRIGGER IF EXISTS trg_glossary_fts_insert;
DROP TRIGGER IF EXISTS trg_glossary_fts_delete;
DROP TRIGGER IF EXISTS trg_glossary_fts_update;
CREATE TRIGGER IF NOT EXISTS trg_glossary_fts_insert AFTER INSERT ON semantic_glossary
BEGIN
    INSERT INTO semantic_glossary_fts(rowid, term_id, canonical_form, definition, variants)
    VALUES (NEW.rowid, NEW.term_id, NEW.canonical_form, NEW.definition, NEW.variants_text);
END;
CREATE TRIGGER IF NOT EXISTS trg_glossary_fts_delete AFTER DELETE ON semantic_glossary
BEGIN
    DELETE FROM semantic_glossary_fts WHERE rowid = OLD.rowid;
END;
CREATE TRIGGER IF NOT EXISTS trg_glossary_fts_update AFTER UPDATE ON semantic_glossary
BEGIN
    DELETE FROM semantic_glossary_fts WHERE rowid = OLD.rowid;
    INSERT INTO semantic_glossary_fts(rowid, term_id, canonical_form, definition, variants)
    VALUES (NEW.rowid, NEW.term_id, NEW.canonical_form, NEW.definition, NEW.variants_text);
END;

DELETE FROM semantic_metric_fts;
INSERT INTO semantic_metric_fts(rowid, metric_id, display_name, definition, synonyms)
SELECT rowid, metric_id, display_name, definition, synonyms_text
FROM semantic_metric;

DELETE FROM semantic_glossary_fts;
INSERT INTO semantic_glossary_fts(rowid, term_id, canonical_form, definition, variants)
SELECT rowid, term_id, canonical_form, definition, variants_text
FROM semantic_glossary;

INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (7, datetime('now'));
"""


class SemanticSqliteDatabase:
    """Shared SQLite database wrapper for semantic repositories."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    @property
    def lock(self) -> threading.Lock:
        return self._lock

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize(self) -> None:
        with self._lock, self.connect() as conn:
            version = self._schema_version(conn)
            if version < 6:
                conn.executescript(_MIGRATION_V6_SQL)
                version = 6
            if version < 7:
                conn.executescript(_MIGRATION_V7_SQL)
            conn.commit()

    @staticmethod
    def _schema_version(conn: sqlite3.Connection) -> int:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        row = conn.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        if row is None or row["version"] is None:
            return 0
        return int(row["version"])


def json_dumps(value: Any) -> str:
    """Serialize JSON with UTF-8 friendly defaults."""

    return json.dumps(value, ensure_ascii=False, default=str)


def json_loads(value: Any, *, default: Any) -> Any:
    """Deserialize JSON with a fallback default."""

    if value in (None, ""):
        return default
    return json.loads(str(value))


def prepare_fts_query(query: str) -> str:
    """Prepare a simple OR-based FTS5 query."""

    terms = [term.strip() for term in query.split() if term.strip()]
    if not terms:
        return '""'
    return " OR ".join(f'"{term}"' for term in terms)
