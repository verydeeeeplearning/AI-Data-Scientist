"""SQLite-backed store for async portfolio manager state."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from ds_agent.domain.portfolio.playbook_candidate import PlaybookCandidate
from ds_agent.domain.portfolio.portfolio_checkpoint import PortfolioCheckpoint
from ds_agent.domain.portfolio.portfolio_entry import (
    BusinessPriority,
    PortfolioEntry,
    PortfolioTransition,
)
from ds_agent.domain.portfolio.wait_condition import WaitCondition, WaitConditionKind
from ds_agent.runtime.transcript_store import get_runtime_storage_root

_SCHEMA_VERSION = 1

_MIGRATION_V1_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_entries (
    entry_id TEXT PRIMARY KEY,
    task_contract_id TEXT NOT NULL,
    quadrant TEXT NOT NULL,
    business_priority TEXT NOT NULL DEFAULT 'P2',
    sla_deadline TEXT,
    parent_run_id TEXT,
    wait_condition_id TEXT,
    monitoring_metric_ref TEXT,
    playbook_candidate_ref TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_transition_at TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS ix_portfolio_entries_quadrant
ON portfolio_entries(quadrant);

CREATE UNIQUE INDEX IF NOT EXISTS ix_portfolio_entries_task
ON portfolio_entries(task_contract_id);

CREATE TABLE IF NOT EXISTS portfolio_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL REFERENCES portfolio_entries(entry_id),
    from_quadrant TEXT,
    to_quadrant TEXT NOT NULL,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_portfolio_transitions_entry
ON portfolio_transitions(entry_id, at DESC);

CREATE TABLE IF NOT EXISTS wait_conditions (
    condition_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    spec_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    deadline TEXT,
    last_checked_at TEXT,
    last_check_result TEXT,
    poll_interval_s INTEGER NOT NULL DEFAULT 60
);

CREATE TABLE IF NOT EXISTS portfolio_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    step_index INTEGER NOT NULL DEFAULT 0,
    state_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_portfolio_checkpoints_entry
ON portfolio_checkpoints(entry_id);

CREATE TABLE IF NOT EXISTS playbook_candidates (
    candidate_id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL,
    pattern_signature TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    confidence REAL NOT NULL DEFAULT 0.0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    promoted INTEGER NOT NULL DEFAULT 0
);
"""


class SqlitePortfolioStore:
    """SQLite-backed portfolio store with schema migrations."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    @classmethod
    def for_workspace(cls, workspace_dir: str | None = None) -> SqlitePortfolioStore:
        """Build a store for the given workspace."""
        return cls(get_runtime_storage_root(workspace_dir) / "portfolio.db")

    def _migrate(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'",
        )
        if cur.fetchone() is None:
            current_version = 0
        else:
            cur.execute("SELECT MAX(version) FROM schema_migrations")
            row = cur.fetchone()
            current_version = row[0] if row and row[0] else 0

        if current_version < 1:
            self._conn.executescript(_MIGRATION_V1_SQL)
            self._conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (1, datetime.now(UTC).isoformat()),
            )
            self._conn.commit()

    # ── Portfolio entries ─────────────────────────────────────────────

    def create_entry(self, entry: PortfolioEntry) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO portfolio_entries
                (entry_id, task_contract_id, quadrant, business_priority,
                 sla_deadline, parent_run_id, wait_condition_id,
                 monitoring_metric_ref, playbook_candidate_ref,
                 created_at, updated_at, last_transition_at, tags_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.entry_id,
                    entry.task_contract_id,
                    entry.quadrant,
                    entry.business_priority.value,
                    entry.sla_deadline.isoformat() if entry.sla_deadline else None,
                    entry.parent_run_id,
                    entry.wait_condition_id,
                    entry.monitoring_metric_ref,
                    entry.playbook_candidate_ref,
                    entry.created_at.isoformat(),
                    entry.updated_at.isoformat(),
                    entry.last_transition_at.isoformat(),
                    json.dumps(entry.tags),
                    json.dumps(entry.metadata),
                ),
            )
            self._conn.commit()

    def get_entry(self, entry_id: str) -> PortfolioEntry | None:
        cur = self._conn.execute(
            "SELECT * FROM portfolio_entries WHERE entry_id = ?",
            (entry_id,),
        )
        row = cur.fetchone()
        return self._deserialize_entry(row, cur.description) if row else None

    def get_entry_by_task(self, task_contract_id: str) -> PortfolioEntry | None:
        cur = self._conn.execute(
            "SELECT * FROM portfolio_entries WHERE task_contract_id = ?",
            (task_contract_id,),
        )
        row = cur.fetchone()
        return self._deserialize_entry(row, cur.description) if row else None

    def list_entries(
        self,
        *,
        quadrant: str | None = None,
        limit: int = 50,
    ) -> list[PortfolioEntry]:
        if quadrant:
            cur = self._conn.execute(
                "SELECT * FROM portfolio_entries WHERE quadrant = ? "
                "ORDER BY updated_at DESC LIMIT ?",
                (quadrant, limit),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM portfolio_entries ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
        desc = cur.description
        return [self._deserialize_entry(row, desc) for row in cur.fetchall()]

    def save_entry(self, entry: PortfolioEntry) -> None:
        with self._lock:
            self._conn.execute(
                """UPDATE portfolio_entries SET
                    quadrant = ?, business_priority = ?, sla_deadline = ?,
                    parent_run_id = ?, wait_condition_id = ?,
                    monitoring_metric_ref = ?, playbook_candidate_ref = ?,
                    updated_at = ?, last_transition_at = ?,
                    tags_json = ?, metadata_json = ?
                WHERE entry_id = ?""",
                (
                    entry.quadrant,
                    entry.business_priority.value,
                    entry.sla_deadline.isoformat() if entry.sla_deadline else None,
                    entry.parent_run_id,
                    entry.wait_condition_id,
                    entry.monitoring_metric_ref,
                    entry.playbook_candidate_ref,
                    entry.updated_at.isoformat(),
                    entry.last_transition_at.isoformat(),
                    json.dumps(entry.tags),
                    json.dumps(entry.metadata),
                    entry.entry_id,
                ),
            )
            self._conn.commit()

    # ── Transitions ──────────────────────────────────────────────────

    def record_transition(
        self,
        entry_id: str,
        transition: PortfolioTransition,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO portfolio_transitions
                (entry_id, from_quadrant, to_quadrant, reason, actor, at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    entry_id,
                    transition.from_quadrant,
                    transition.to_quadrant,
                    transition.reason,
                    transition.actor,
                    transition.at.isoformat(),
                ),
            )
            self._conn.commit()

    def list_transitions(
        self,
        entry_id: str,
        *,
        limit: int = 50,
    ) -> list[PortfolioTransition]:
        cur = self._conn.execute(
            "SELECT from_quadrant, to_quadrant, reason, actor, at "
            "FROM portfolio_transitions WHERE entry_id = ? "
            "ORDER BY at DESC LIMIT ?",
            (entry_id, limit),
        )
        return [
            PortfolioTransition(
                from_quadrant=row[0],
                to_quadrant=row[1],
                reason=row[2],
                actor=row[3],
                at=datetime.fromisoformat(row[4]),
            )
            for row in cur.fetchall()
        ]

    # ── Wait conditions ──────────────────────────────────────────────

    def save_wait_condition(self, condition: WaitCondition) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO wait_conditions
                (condition_id, kind, spec_json, created_at, deadline,
                 last_checked_at, last_check_result, poll_interval_s)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    condition.condition_id,
                    condition.kind.value,
                    json.dumps(condition.spec),
                    condition.created_at.isoformat(),
                    condition.deadline.isoformat() if condition.deadline else None,
                    condition.last_checked_at.isoformat() if condition.last_checked_at else None,
                    condition.last_check_result,
                    condition.poll_interval_s,
                ),
            )
            self._conn.commit()

    def get_wait_condition(self, condition_id: str) -> WaitCondition | None:
        cur = self._conn.execute(
            "SELECT * FROM wait_conditions WHERE condition_id = ?",
            (condition_id,),
        )
        row = cur.fetchone()
        return self._deserialize_wait_condition(row) if row else None

    def list_pending_wait_conditions(self, *, limit: int = 50) -> list[WaitCondition]:
        cur = self._conn.execute(
            "SELECT * FROM wait_conditions "
            "WHERE last_check_result IS NULL OR last_check_result = 'pending' "
            "ORDER BY created_at LIMIT ?",
            (limit,),
        )
        return [self._deserialize_wait_condition(row) for row in cur.fetchall()]

    # ── Checkpoints ──────────────────────────────────────────────────

    def save_checkpoint(self, checkpoint: PortfolioCheckpoint) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO portfolio_checkpoints
                (checkpoint_id, entry_id, run_id, step_index, state_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    checkpoint.checkpoint_id,
                    checkpoint.entry_id,
                    checkpoint.run_id,
                    checkpoint.step_index,
                    json.dumps(checkpoint.state_json),
                    checkpoint.created_at.isoformat(),
                ),
            )
            self._conn.commit()

    def get_checkpoint(self, entry_id: str) -> PortfolioCheckpoint | None:
        cur = self._conn.execute(
            "SELECT * FROM portfolio_checkpoints WHERE entry_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (entry_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return PortfolioCheckpoint(
            checkpoint_id=row[0],
            entry_id=row[1],
            run_id=row[2],
            step_index=row[3],
            state_json=json.loads(row[4]) if row[4] else {},
            created_at=datetime.fromisoformat(row[5]),
        )

    # ── Playbook candidates ──────────────────────────────────────────

    def save_playbook_candidate(self, candidate: PlaybookCandidate) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO playbook_candidates
                (candidate_id, entry_id, pattern_signature, description,
                 occurrence_count, confidence, metadata_json, created_at, promoted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    candidate.candidate_id,
                    candidate.entry_id,
                    candidate.pattern_signature,
                    candidate.description,
                    candidate.occurrence_count,
                    candidate.confidence,
                    json.dumps(candidate.metadata),
                    candidate.created_at.isoformat(),
                    1 if candidate.promoted else 0,
                ),
            )
            self._conn.commit()

    def list_playbook_candidates(self, *, limit: int = 20) -> list[PlaybookCandidate]:
        cur = self._conn.execute(
            "SELECT * FROM playbook_candidates ORDER BY confidence DESC LIMIT ?",
            (limit,),
        )
        return [
            PlaybookCandidate(
                candidate_id=row[0],
                entry_id=row[1],
                pattern_signature=row[2],
                description=row[3],
                occurrence_count=row[4],
                confidence=row[5],
                metadata=json.loads(row[6]) if row[6] else {},
                created_at=datetime.fromisoformat(row[7]),
                promoted=bool(row[8]),
            )
            for row in cur.fetchall()
        ]

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _deserialize_entry(row: tuple, description: object) -> PortfolioEntry:
        return PortfolioEntry(
            entry_id=row[0],
            task_contract_id=row[1],
            quadrant=row[2],
            business_priority=BusinessPriority(row[3]),
            sla_deadline=datetime.fromisoformat(row[4]) if row[4] else None,
            parent_run_id=row[5],
            wait_condition_id=row[6],
            monitoring_metric_ref=row[7],
            playbook_candidate_ref=row[8],
            created_at=datetime.fromisoformat(row[9]),
            updated_at=datetime.fromisoformat(row[10]),
            last_transition_at=datetime.fromisoformat(row[11]),
            tags=json.loads(row[12]) if row[12] else [],
            metadata=json.loads(row[13]) if row[13] else {},
        )

    @staticmethod
    def _deserialize_wait_condition(row: tuple) -> WaitCondition:
        return WaitCondition(
            condition_id=row[0],
            kind=WaitConditionKind(row[1]),
            spec=json.loads(row[2]) if row[2] else {},
            created_at=datetime.fromisoformat(row[3]),
            deadline=datetime.fromisoformat(row[4]) if row[4] else None,
            last_checked_at=datetime.fromisoformat(row[5]) if row[5] else None,
            last_check_result=row[6],
            poll_interval_s=row[7],
        )
