"""SQLite-backed store for self-improvement governance."""

from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from ds_agent.domain.learning.deprecation_record import (
    DeprecationMode,
    DeprecationReason,
    DeprecationRecord,
)
from ds_agent.domain.learning.learning_item import (
    ConflictRef,
    Evidence,
    LearningItem,
    LearningItemStatus,
    LearningItemType,
    SourceInfo,
)
from ds_agent.domain.learning.promotion_record import PromotionRecord
from ds_agent.domain.learning.review_event import (
    ReviewChecklist,
    ReviewDecision,
    ReviewEvent,
)
from ds_agent.runtime.transcript_store import get_runtime_storage_root

_SCHEMA_VERSION = 13

_MIGRATION_V1_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learning_items (
    item_id TEXT PRIMARY KEY,
    item_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    signature TEXT NOT NULL,
    source_json TEXT NOT NULL DEFAULT '{}',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    conflict_refs_json TEXT NOT NULL DEFAULT '[]',
    tags_json TEXT NOT NULL DEFAULT '[]',
    scope TEXT NOT NULL DEFAULT 'project',
    review_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_learning_items_signature
ON learning_items(signature);

CREATE INDEX IF NOT EXISTS ix_learning_items_status
ON learning_items(status);

CREATE INDEX IF NOT EXISTS ix_learning_items_type
ON learning_items(item_type);

CREATE TABLE IF NOT EXISTS review_events (
    event_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reviewer TEXT NOT NULL DEFAULT 'system',
    checklist_json TEXT,
    comment TEXT NOT NULL DEFAULT '',
    modifications_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_review_events_item
ON review_events(item_id, created_at DESC);

CREATE TABLE IF NOT EXISTS promotion_records (
    record_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    eval_score REAL NOT NULL,
    eval_threshold REAL NOT NULL,
    promoted_asset_ref TEXT NOT NULL DEFAULT '',
    rollback_ref TEXT NOT NULL DEFAULT '',
    promoted_at TEXT NOT NULL,
    promoted_by TEXT NOT NULL DEFAULT 'system',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS ix_promotion_records_item
ON promotion_records(item_id);

CREATE TABLE IF NOT EXISTS deprecation_records (
    record_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'immediate',
    failure_count INTEGER NOT NULL DEFAULT 0,
    grace_until TEXT,
    deprecated_at TEXT NOT NULL,
    deprecated_by TEXT NOT NULL DEFAULT 'system',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS ix_deprecation_records_item
ON deprecation_records(item_id);
"""


# v13 migration: add an audit ``description`` column to ``schema_migrations``
# so the central migration inventory/runner (see
# ``ds_agent.infrastructure.migration.sqlite_migrations``) can record the
# rationale for each applied migration without a schema churn.
#
# Rationale captured in
# ``Docs/qa_run_2026-04-17/S4_v13_migration/RECOMMENDATIONS.md``.
_LEARNING_STORE_V13_DESCRIPTION = (
    "v13: add audit description column to schema_migrations for central runner traceability"
)


class SqliteLearningStore:
    """SQLite-backed learning governance store."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    @classmethod
    def for_workspace(cls, workspace_dir: str | None = None) -> SqliteLearningStore:
        return cls(get_runtime_storage_root(workspace_dir) / "learning.db")

    def _migrate(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'",
        )
        if cur.fetchone() is None:
            current = 0
        else:
            cur.execute("SELECT MAX(version) FROM schema_migrations")
            row = cur.fetchone()
            current = row[0] if row and row[0] else 0

        if current < 1:
            self._conn.executescript(_MIGRATION_V1_SQL)
            self._conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (1, datetime.now(UTC).isoformat()),
            )
            self._conn.commit()
            current = 1

        if current < 13:
            self._apply_v13()

    def _apply_v13(self) -> None:
        """Apply v13 migration: add ``description`` audit column idempotently.

        v13 is the terminal version tracked by the central migration runner
        (``ds_agent.infrastructure.migration.sqlite_migrations``). The change
        is additive: a nullable ``description`` column on ``schema_migrations``
        with a backfill for the existing row(s). This is intentionally
        defensive — it adds observability without altering any domain table.
        """
        cols = {
            str(row[1])
            for row in self._conn.execute("PRAGMA table_info(schema_migrations)").fetchall()
        }
        if "description" not in cols:
            self._conn.execute("ALTER TABLE schema_migrations ADD COLUMN description TEXT")
        # Backfill v1 description so historic rows are explicable.
        self._conn.execute(
            "UPDATE schema_migrations SET description = ? "
            "WHERE version = 1 AND (description IS NULL OR description = '')",
            ("v1: initial learning governance schema",),
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO schema_migrations (version, applied_at, description) "
            "VALUES (?, ?, ?)",
            (13, datetime.now(UTC).isoformat(), _LEARNING_STORE_V13_DESCRIPTION),
        )
        self._conn.commit()

    # ── Learning items ───────────────────────────────────────────────

    def save_item(self, item: LearningItem) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO learning_items
                (item_id, item_type, status, title, content, signature,
                 source_json, evidence_json, conflict_refs_json, tags_json,
                 scope, review_count, created_at, updated_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item.item_id,
                    item.item_type.value,
                    item.status.value,
                    item.title,
                    item.content,
                    item.signature,
                    item.source.model_dump_json(),
                    json.dumps([e.model_dump(mode="json") for e in item.evidence]),
                    json.dumps([c.model_dump(mode="json") for c in item.conflict_refs]),
                    json.dumps(item.tags),
                    item.scope,
                    item.review_count,
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                    json.dumps(item.metadata),
                ),
            )
            self._conn.commit()

    def get_item(self, item_id: str) -> LearningItem | None:
        cur = self._conn.execute(
            "SELECT * FROM learning_items WHERE item_id = ?",
            (item_id,),
        )
        row = cur.fetchone()
        return self._deserialize_item(row) if row else None

    def list_items(
        self,
        *,
        status: LearningItemStatus | None = None,
        item_type: LearningItemType | None = None,
        limit: int = 50,
    ) -> list[LearningItem]:
        clauses: list[str] = []
        params: list[object] = []
        if status:
            clauses.append("status = ?")
            params.append(status.value)
        if item_type:
            clauses.append("item_type = ?")
            params.append(item_type.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur = self._conn.execute(
            f"SELECT * FROM learning_items {where} ORDER BY updated_at DESC LIMIT ?",
            params,
        )
        return [self._deserialize_item(row) for row in cur.fetchall()]

    def find_by_signature(self, signature: str) -> LearningItem | None:
        cur = self._conn.execute(
            "SELECT * FROM learning_items WHERE signature = ?",
            (signature,),
        )
        row = cur.fetchone()
        return self._deserialize_item(row) if row else None

    def list_monitored_items(
        self,
        *,
        item_type: LearningItemType | None = None,
        limit: int = 50,
    ) -> list[LearningItem]:
        return self.list_items(
            status=LearningItemStatus.MONITORED,
            item_type=item_type,
            limit=limit,
        )

    # ── Review events ────────────────────────────────────────────────

    def save_review_event(self, event: ReviewEvent) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO review_events
                (event_id, item_id, decision, reviewer,
                 checklist_json, comment, modifications_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.event_id,
                    event.item_id,
                    event.decision.value,
                    event.reviewer,
                    event.checklist.model_dump_json() if event.checklist else None,
                    event.comment,
                    json.dumps(event.modifications),
                    event.created_at.isoformat(),
                ),
            )
            self._conn.commit()

    def list_review_events(
        self,
        item_id: str,
        *,
        limit: int = 20,
    ) -> list[ReviewEvent]:
        cur = self._conn.execute(
            "SELECT * FROM review_events WHERE item_id = ? ORDER BY created_at DESC LIMIT ?",
            (item_id, limit),
        )
        return [self._deserialize_review_event(row) for row in cur.fetchall()]

    # ── Promotion records ────────────────────────────────────────────

    def save_promotion_record(self, record: PromotionRecord) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO promotion_records
                (record_id, item_id, item_type, eval_score, eval_threshold,
                 promoted_asset_ref, rollback_ref, promoted_at, promoted_by,
                 metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.record_id,
                    record.item_id,
                    record.item_type.value,
                    record.eval_score,
                    record.eval_threshold,
                    record.promoted_asset_ref,
                    record.rollback_ref,
                    record.promoted_at.isoformat(),
                    record.promoted_by,
                    json.dumps(record.metadata),
                ),
            )
            self._conn.commit()

    def get_promotion_record(self, item_id: str) -> PromotionRecord | None:
        cur = self._conn.execute(
            "SELECT * FROM promotion_records WHERE item_id = ? ORDER BY promoted_at DESC LIMIT 1",
            (item_id,),
        )
        row = cur.fetchone()
        return self._deserialize_promotion_record(row) if row else None

    def list_promotion_records(self, *, limit: int = 50) -> list[PromotionRecord]:
        cur = self._conn.execute(
            "SELECT * FROM promotion_records ORDER BY promoted_at DESC LIMIT ?",
            (limit,),
        )
        return [self._deserialize_promotion_record(row) for row in cur.fetchall()]

    # ── Deprecation records ──────────────────────────────────────────

    def save_deprecation_record(self, record: DeprecationRecord) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO deprecation_records
                (record_id, item_id, reason, mode, failure_count,
                 grace_until, deprecated_at, deprecated_by, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.record_id,
                    record.item_id,
                    record.reason.value,
                    record.mode.value,
                    record.failure_count,
                    record.grace_until.isoformat() if record.grace_until else None,
                    record.deprecated_at.isoformat(),
                    record.deprecated_by,
                    record.notes,
                ),
            )
            self._conn.commit()

    # ── Atomic multi-row writes ──────────────────────────────────────
    #
    # Implements ``application.ports.learning_store_port.LearningStoreAtomicPort``.
    # The port lives in the application layer so the use case does not
    # take an infrastructure dependency; this adapter satisfies it by
    # committing both rows inside a single transaction.
    #
    # History:
    # - ``save_item_and_deprecation``: S6 (Fix Sprint R3, 2026-04-17)
    #   closes FAIL-B11-8 rollback atomicity. See
    #   ``Docs/qa_run_2026-04-17/S6_rollback_atomicity/``.
    # - ``save_promotion_and_item``: S9 (Fix Sprint R4 follow-up, 2026-04-18)
    #   closes the R-1 phantom-promotion audit split identified in
    #   S6 RECOMMENDATIONS §R-1. See
    #   ``Docs/qa_run_2026-04-17/S9_r1_r2_atomicity/``.

    def save_review_event_and_item(
        self,
        *,
        event: ReviewEvent,
        item: LearningItem,
    ) -> None:
        """Atomically persist a review event and the reviewed item.

        S10 addresses R-3: the review event stream and the item status
        transition MUST land together. ``review_events`` uses
        ``INSERT`` (append-only, event_id is a primary key), while
        ``learning_items`` uses ``INSERT OR REPLACE`` (upsert the row).
        Both run inside one ``BEGIN IMMEDIATE`` / ``COMMIT`` — ROLLBACK
        on any error reverts both.
        """
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    """INSERT INTO review_events
                    (event_id, item_id, decision, reviewer,
                     checklist_json, comment, modifications_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event.event_id,
                        event.item_id,
                        event.decision.value,
                        event.reviewer,
                        event.checklist.model_dump_json() if event.checklist else None,
                        event.comment,
                        json.dumps(event.modifications),
                        event.created_at.isoformat(),
                    ),
                )
                self._conn.execute(
                    """INSERT OR REPLACE INTO learning_items
                    (item_id, item_type, status, title, content, signature,
                     source_json, evidence_json, conflict_refs_json, tags_json,
                     scope, review_count, created_at, updated_at, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item.item_id,
                        item.item_type.value,
                        item.status.value,
                        item.title,
                        item.content,
                        item.signature,
                        item.source.model_dump_json(),
                        json.dumps([e.model_dump(mode="json") for e in item.evidence]),
                        json.dumps([c.model_dump(mode="json") for c in item.conflict_refs]),
                        json.dumps(item.tags),
                        item.scope,
                        item.review_count,
                        item.created_at.isoformat(),
                        item.updated_at.isoformat(),
                        json.dumps(item.metadata),
                    ),
                )
                self._conn.commit()
            except BaseException:
                with contextlib.suppress(sqlite3.Error):
                    self._conn.rollback()
                raise

    def save_promotion_and_item(
        self,
        *,
        promotion: PromotionRecord,
        item: LearningItem,
    ) -> None:
        """Atomically persist a promotion record and the promoted item.

        Same ``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK`` shape as
        ``save_item_and_deprecation`` — co-commits
        ``promotion_records`` and ``learning_items`` rows. Either both
        land, or neither does. Closes the R-1 audit-split described in
        S6 RECOMMENDATIONS.
        """
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    """INSERT OR REPLACE INTO promotion_records
                    (record_id, item_id, item_type, eval_score, eval_threshold,
                     promoted_asset_ref, rollback_ref, promoted_at, promoted_by,
                     metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        promotion.record_id,
                        promotion.item_id,
                        promotion.item_type.value,
                        promotion.eval_score,
                        promotion.eval_threshold,
                        promotion.promoted_asset_ref,
                        promotion.rollback_ref,
                        promotion.promoted_at.isoformat(),
                        promotion.promoted_by,
                        json.dumps(promotion.metadata),
                    ),
                )
                self._conn.execute(
                    """INSERT OR REPLACE INTO learning_items
                    (item_id, item_type, status, title, content, signature,
                     source_json, evidence_json, conflict_refs_json, tags_json,
                     scope, review_count, created_at, updated_at, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item.item_id,
                        item.item_type.value,
                        item.status.value,
                        item.title,
                        item.content,
                        item.signature,
                        item.source.model_dump_json(),
                        json.dumps([e.model_dump(mode="json") for e in item.evidence]),
                        json.dumps([c.model_dump(mode="json") for c in item.conflict_refs]),
                        json.dumps(item.tags),
                        item.scope,
                        item.review_count,
                        item.created_at.isoformat(),
                        item.updated_at.isoformat(),
                        json.dumps(item.metadata),
                    ),
                )
                self._conn.commit()
            except BaseException:
                with contextlib.suppress(sqlite3.Error):
                    self._conn.rollback()
                raise

    def save_item_and_deprecation(
        self,
        *,
        item: LearningItem,
        deprecation: DeprecationRecord,
    ) -> None:
        """Atomically persist an item update and its deprecation record.

        Uses ``BEGIN IMMEDIATE`` to grab the write lock up-front so no
        other writer can interleave between the two ``INSERT`` s. If
        either write raises, the surrounding transaction is rolled back
        and the exception is re-raised verbatim — leaving both rows as
        they were before the call.

        This closes the audit-trail-split failure documented in
        ``Docs/qa_run_2026-04-17/B11_portfolio_learning/B11_rollback_atomicity_sqlite_probe.json``.
        """
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    """INSERT OR REPLACE INTO learning_items
                    (item_id, item_type, status, title, content, signature,
                     source_json, evidence_json, conflict_refs_json, tags_json,
                     scope, review_count, created_at, updated_at, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item.item_id,
                        item.item_type.value,
                        item.status.value,
                        item.title,
                        item.content,
                        item.signature,
                        item.source.model_dump_json(),
                        json.dumps([e.model_dump(mode="json") for e in item.evidence]),
                        json.dumps([c.model_dump(mode="json") for c in item.conflict_refs]),
                        json.dumps(item.tags),
                        item.scope,
                        item.review_count,
                        item.created_at.isoformat(),
                        item.updated_at.isoformat(),
                        json.dumps(item.metadata),
                    ),
                )
                self._conn.execute(
                    """INSERT OR REPLACE INTO deprecation_records
                    (record_id, item_id, reason, mode, failure_count,
                     grace_until, deprecated_at, deprecated_by, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        deprecation.record_id,
                        deprecation.item_id,
                        deprecation.reason.value,
                        deprecation.mode.value,
                        deprecation.failure_count,
                        deprecation.grace_until.isoformat() if deprecation.grace_until else None,
                        deprecation.deprecated_at.isoformat(),
                        deprecation.deprecated_by,
                        deprecation.notes,
                    ),
                )
                self._conn.commit()
            except BaseException:
                # Roll back so neither row is observable to other readers.
                # If rollback itself fails there is nothing more the
                # adapter can do; the original exception is still the
                # one the caller needs to see.
                with contextlib.suppress(sqlite3.Error):
                    self._conn.rollback()
                raise

    def get_deprecation_record(self, item_id: str) -> DeprecationRecord | None:
        cur = self._conn.execute(
            "SELECT * FROM deprecation_records WHERE item_id = ? "
            "ORDER BY deprecated_at DESC LIMIT 1",
            (item_id,),
        )
        row = cur.fetchone()
        return self._deserialize_deprecation_record(row) if row else None

    def list_deprecation_records(self, *, limit: int = 50) -> list[DeprecationRecord]:
        cur = self._conn.execute(
            "SELECT * FROM deprecation_records ORDER BY deprecated_at DESC LIMIT ?",
            (limit,),
        )
        return [self._deserialize_deprecation_record(row) for row in cur.fetchall()]

    # ── Deserialization helpers ───────────────────────────────────────

    @staticmethod
    def _deserialize_item(row: tuple) -> LearningItem:
        return LearningItem(
            item_id=row[0],
            item_type=LearningItemType(row[1]),
            status=LearningItemStatus(row[2]),
            title=row[3],
            content=row[4],
            signature=row[5],
            source=SourceInfo.model_validate_json(row[6]) if row[6] else SourceInfo(),
            evidence=[Evidence.model_validate(e) for e in json.loads(row[7] or "[]")],
            conflict_refs=[ConflictRef.model_validate(c) for c in json.loads(row[8] or "[]")],
            tags=json.loads(row[9] or "[]"),
            scope=row[10],
            review_count=row[11],
            created_at=datetime.fromisoformat(row[12]),
            updated_at=datetime.fromisoformat(row[13]),
            metadata=json.loads(row[14] or "{}"),
        )

    @staticmethod
    def _deserialize_review_event(row: tuple) -> ReviewEvent:
        return ReviewEvent(
            event_id=row[0],
            item_id=row[1],
            decision=ReviewDecision(row[2]),
            reviewer=row[3],
            checklist=(ReviewChecklist.model_validate_json(row[4]) if row[4] else None),
            comment=row[5],
            modifications=json.loads(row[6] or "{}"),
            created_at=datetime.fromisoformat(row[7]),
        )

    @staticmethod
    def _deserialize_promotion_record(row: tuple) -> PromotionRecord:
        return PromotionRecord(
            record_id=row[0],
            item_id=row[1],
            item_type=LearningItemType(row[2]),
            eval_score=row[3],
            eval_threshold=row[4],
            promoted_asset_ref=row[5],
            rollback_ref=row[6],
            promoted_at=datetime.fromisoformat(row[7]),
            promoted_by=row[8],
            metadata=json.loads(row[9] or "{}"),
        )

    @staticmethod
    def _deserialize_deprecation_record(row: tuple) -> DeprecationRecord:
        return DeprecationRecord(
            record_id=row[0],
            item_id=row[1],
            reason=DeprecationReason(row[2]),
            mode=DeprecationMode(row[3]),
            failure_count=row[4],
            grace_until=(datetime.fromisoformat(row[5]) if row[5] else None),
            deprecated_at=datetime.fromisoformat(row[6]),
            deprecated_by=row[7],
            notes=row[8],
        )
