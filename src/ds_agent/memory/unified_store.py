"""UnifiedMemoryStore — SQLite + FTS5 persistent memory.

Infrastructure layer implementation of MemoryStorePort.
Provides full-text search, type filtering, confidence decay,
and duplicate detection (key+type upsert).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from ds_agent.domain.entities.memory import MemoryEntry, MemoryType

_DEFAULT_DB_DIR = Path("data/memory")
_DEFAULT_DB_NAME = "unified_memory.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    key TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT DEFAULT '[]',
    confidence REAL DEFAULT 1.0,
    source_session_id TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_key_type
    ON memories(key, type);

CREATE INDEX IF NOT EXISTS idx_memories_type
    ON memories(type);
"""

_FTS_SCHEMA_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    key, content, tags,
    content='memories',
    content_rowid='rowid'
);
"""

_FTS_TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, key, content, tags)
    VALUES (new.rowid, new.key, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, key, content, tags)
    VALUES('delete', old.rowid, old.key, old.content, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, key, content, tags)
    VALUES('delete', old.rowid, old.key, old.content, old.tags);
    INSERT INTO memories_fts(rowid, key, content, tags)
    VALUES (new.rowid, new.key, new.content, new.tags);
END;
"""


class UnifiedMemoryStore:
    """SQLite + FTS5 implementation of MemoryStorePort.

    Thread-safe via threading.Lock. Supports full-text search,
    type filtering, and key+type based upsert.
    """

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            _DEFAULT_DB_DIR.mkdir(parents=True, exist_ok=True)
            db_path = str(_DEFAULT_DB_DIR / _DEFAULT_DB_NAME)
        else:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.executescript(_SCHEMA_SQL)
                conn.executescript(_FTS_SCHEMA_SQL)
                conn.executescript(_FTS_TRIGGERS_SQL)
                conn.commit()
            finally:
                conn.close()

    def store(self, entry: MemoryEntry) -> str:
        """Store or upsert a memory entry. Returns the entry ID."""
        tags_json = json.dumps(entry.tags)

        with self._lock:
            conn = self._get_conn()
            try:
                # Check for existing entry with same key+type
                row = conn.execute(
                    "SELECT id FROM memories WHERE key = ? AND type = ?",
                    (entry.key, entry.type),
                ).fetchone()

                if row:
                    # Upsert: update existing
                    existing_id = row["id"]
                    conn.execute(
                        """UPDATE memories SET content = ?, tags = ?,
                           confidence = ?, source_session_id = ?,
                           updated_at = ? WHERE id = ?""",
                        (
                            entry.content,
                            tags_json,
                            entry.confidence,
                            entry.source_session_id,
                            entry.updated_at,
                            existing_id,
                        ),
                    )
                    conn.commit()
                    return str(existing_id)
                else:
                    # Insert new — preserve entry timestamps
                    conn.execute(
                        """INSERT INTO memories
                           (id, type, key, content, tags, confidence,
                            source_session_id, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            entry.id,
                            entry.type,
                            entry.key,
                            entry.content,
                            tags_json,
                            entry.confidence,
                            entry.source_session_id,
                            entry.created_at,
                            entry.updated_at,
                        ),
                    )
                    conn.commit()
                    return entry.id
            finally:
                conn.close()

    def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        max_results: int = 5,
        session_id: str | None = None,
    ) -> list[MemoryEntry]:
        """Full-text search with optional type + session filtering."""
        clauses: list[str] = []
        params: list[object] = []
        if memory_type is not None:
            clauses.append("m.type = ?")
            params.append(memory_type)
        if session_id is not None:
            clauses.append("m.source_session_id = ?")
            params.append(session_id)

        with self._lock:
            conn = self._get_conn()
            try:
                if query.strip() == "*":
                    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
                    sql = f"SELECT m.* FROM memories m{where} ORDER BY m.updated_at DESC LIMIT ?"
                    rows = conn.execute(sql, (*params, max_results)).fetchall()
                else:
                    fts_query = self._prepare_fts_query(query)
                    match_clauses = ["memories_fts MATCH ?", *clauses]
                    sql = (
                        "SELECT m.* FROM memories m "
                        "JOIN memories_fts f ON m.rowid = f.rowid "
                        f"WHERE {' AND '.join(match_clauses)} "
                        "ORDER BY rank LIMIT ?"
                    )
                    rows = conn.execute(sql, (fts_query, *params, max_results)).fetchall()

                return [self._row_to_entry(row) for row in rows]
            finally:
                conn.close()

    def search_sessions(
        self,
        query: str,
        session_id: str | None = None,
        max_results: int = 10,
    ) -> list[MemoryEntry]:
        """Search session-scoped memories.

        Restricted to MemoryType.SESSION; optional session_id filter narrows to
        a specific session. `query="*"` lists recent session entries.
        """
        return self.search(
            query=query,
            memory_type=MemoryType.SESSION,
            max_results=max_results,
            session_id=session_id,
        )

    def get(self, entry_id: str) -> MemoryEntry | None:
        """Get a single entry by ID."""
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT * FROM memories WHERE id = ?", (entry_id,)).fetchone()
                return self._row_to_entry(row) if row else None
            finally:
                conn.close()

    def update(
        self,
        entry_id: str,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> bool:
        """Update an existing entry. Returns True if found and updated."""
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute("SELECT id FROM memories WHERE id = ?", (entry_id,)).fetchone()
                if not row:
                    return False

                updates: list[str] = []
                params: list[object] = []
                if content is not None:
                    updates.append("content = ?")
                    params.append(content)
                if tags is not None:
                    updates.append("tags = ?")
                    params.append(json.dumps(tags))

                updates.append("updated_at = ?")
                params.append(time.time())
                params.append(entry_id)

                conn.execute(
                    f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
                    params,
                )
                conn.commit()
                return True
            finally:
                conn.close()

    def delete(self, entry_id: str) -> bool:
        """Delete an entry. Returns True if found and deleted."""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute("DELETE FROM memories WHERE id = ?", (entry_id,))
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def list_by_type(self, memory_type: MemoryType, limit: int = 50) -> list[MemoryEntry]:
        """List all entries of a given type."""
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE type = ? ORDER BY updated_at DESC LIMIT ?",
                    (memory_type, limit),
                ).fetchall()
                return [self._row_to_entry(row) for row in rows]
            finally:
                conn.close()

    @staticmethod
    def _prepare_fts_query(query: str) -> str:
        """Prepare a query string for FTS5 MATCH.

        Wraps individual terms in double quotes for phrase safety,
        joins with OR for broader matching.
        """
        terms = query.strip().split()
        if not terms:
            return '""'
        # Quote each term and join with OR
        quoted = [f'"{t}"' for t in terms]
        return " OR ".join(quoted)

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
        """Convert a SQLite row to a MemoryEntry."""
        tags_raw = row["tags"]
        try:
            tags = json.loads(tags_raw) if tags_raw else []
        except (json.JSONDecodeError, TypeError):
            tags = []

        return MemoryEntry(
            id=row["id"],
            type=MemoryType(row["type"]),
            key=row["key"],
            content=row["content"],
            tags=tags,
            confidence=row["confidence"],
            source_session_id=row["source_session_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
