"""SQLite-backed store for result cards."""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from ds_agent.domain.result_card import ResultCard, ResultCardAdapter, clone_result_card
from ds_agent.runtime.transcript_store import get_runtime_storage_root

_SCHEMA_VERSION = 1

_MIGRATION_V1_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS result_cards (
    card_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    tool_call_id TEXT,
    card_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    pinned INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    pinned_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_result_cards_session
ON result_cards(session_id, pinned DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_result_cards_run
ON result_cards(run_id);

CREATE INDEX IF NOT EXISTS idx_result_cards_message
ON result_cards(message_id);
"""


@runtime_checkable
class CardStore(Protocol):
    """Storage contract for result cards."""

    def save_card(self, session_id: str, card: ResultCard) -> ResultCard: ...

    def get_card(self, card_id: str) -> ResultCard | None: ...

    def list_cards_by_session(
        self,
        session_id: str,
        *,
        limit: int = 100,
        include_archived: bool = False,
    ) -> list[ResultCard]: ...

    def pin_card(self, card_id: str, *, pinned: bool = True) -> ResultCard: ...


class SqliteCardStore:
    """SQLite implementation of the result-card store."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    @property
    def db_path(self) -> Path:
        return self._db_path

    @classmethod
    def for_workspace(cls, workspace_dir: str | None = None) -> SqliteCardStore:
        """Create a store in the workspace runtime directory."""

        return cls(get_runtime_storage_root(workspace_dir) / "result_cards.db")

    def save_card(self, session_id: str, card: ResultCard) -> ResultCard:
        """Insert or replace one card payload."""

        now = datetime.now(UTC).isoformat()
        payload_json = card.model_dump_json(by_alias=True)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO result_cards (
                    card_id, session_id, run_id, message_id, tool_call_id,
                    card_type, payload_json, created_at, updated_at, pinned,
                    archived, pinned_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card.card_id,
                    session_id,
                    card.source.run_id,
                    card.source.message_id,
                    card.source.tool_call_id,
                    card.type,
                    payload_json,
                    card.created_at.isoformat(),
                    now,
                    1 if card.pinned else 0,
                    1 if card.archived else 0,
                    now if card.pinned else None,
                ),
            )
            conn.commit()
        return card

    def get_card(self, card_id: str) -> ResultCard | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json, pinned, archived FROM result_cards WHERE card_id = ?",
                (card_id,),
            ).fetchone()
        if row is None:
            return None
        card = self._deserialize_card(row["payload_json"])
        return card.model_copy(
            update={
                "pinned": bool(row["pinned"]),
                "archived": bool(row["archived"]),
            },
        )

    def list_cards_by_session(
        self,
        session_id: str,
        *,
        limit: int = 100,
        include_archived: bool = False,
    ) -> list[ResultCard]:
        where = "session_id = ?"
        params: list[object] = [session_id]
        if not include_archived:
            where += " AND archived = 0"
        params.append(limit)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT payload_json, pinned, archived
                FROM result_cards
                WHERE {where}
                ORDER BY
                    pinned DESC,
                    COALESCE(pinned_at, created_at) DESC,
                    created_at DESC,
                    card_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        cards: list[ResultCard] = []
        for row in rows:
            card = self._deserialize_card(row["payload_json"])
            cards.append(
                card.model_copy(
                    update={
                        "pinned": bool(row["pinned"]),
                        "archived": bool(row["archived"]),
                    },
                ),
            )
        return cards

    def pin_card(self, card_id: str, *, pinned: bool = True) -> ResultCard:
        now = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM result_cards WHERE card_id = ?",
                (card_id,),
            ).fetchone()
            if row is None:
                raise LookupError(f"Card not found: {card_id}")
            card = self._deserialize_card(row["payload_json"])
            updated_card = clone_result_card(card, pinned=pinned)
            conn.execute(
                """
                UPDATE result_cards
                SET payload_json = ?, pinned = ?, pinned_at = ?, updated_at = ?
                WHERE card_id = ?
                """,
                (
                    updated_card.model_dump_json(by_alias=True),
                    1 if pinned else 0,
                    now if pinned else None,
                    now,
                    card_id,
                ),
            )
            conn.commit()
        return updated_card

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            version = self._schema_version(conn)
            if version < _SCHEMA_VERSION:
                conn.executescript(_MIGRATION_V1_SQL)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (_SCHEMA_VERSION, datetime.now(UTC).isoformat()),
                )
                conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @staticmethod
    def _schema_version(conn: sqlite3.Connection) -> int:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """,
        )
        row = conn.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        if row is None or row["version"] is None:
            return 0
        return int(row["version"])

    @staticmethod
    def _deserialize_card(payload_json: str) -> ResultCard:
        return ResultCardAdapter.validate_json(payload_json)
