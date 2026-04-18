"""SQLite-backed store for Decision OS promotion decisions."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

from ds_agent.domain.entities.promotion import PromotionDecision

_MIGRATION_V1_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promotion_decisions (
    decision_id TEXT PRIMARY KEY,
    candidate_run_id TEXT NOT NULL,
    candidate_model_id TEXT NOT NULL,
    target_stage TEXT NOT NULL,
    policy_checks_json TEXT NOT NULL DEFAULT '[]',
    approvals_json TEXT NOT NULL DEFAULT '[]',
    chain_state TEXT NOT NULL,
    rollback_plan_ref TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_promotion_decisions_run
    ON promotion_decisions(candidate_run_id, created_at DESC);

INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (1, datetime('now'));
"""


class SqlitePromotionDecisionStore:
    """SQLite implementation of the Decision OS promotion-decision store."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    @classmethod
    def for_workspace(cls, workspace_dir: str | None = None) -> SqlitePromotionDecisionStore:
        """Create a store at the default Decision OS location for a workspace."""

        return cls(_default_db_path(workspace_dir))

    def save(self, decision: PromotionDecision) -> None:
        payload = decision.model_dump(mode="json")
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO promotion_decisions (
                    decision_id,
                    candidate_run_id,
                    candidate_model_id,
                    target_stage,
                    policy_checks_json,
                    approvals_json,
                    chain_state,
                    rollback_plan_ref,
                    created_at,
                    resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(decision_id) DO UPDATE SET
                    candidate_run_id = excluded.candidate_run_id,
                    candidate_model_id = excluded.candidate_model_id,
                    target_stage = excluded.target_stage,
                    policy_checks_json = excluded.policy_checks_json,
                    approvals_json = excluded.approvals_json,
                    chain_state = excluded.chain_state,
                    rollback_plan_ref = excluded.rollback_plan_ref,
                    created_at = excluded.created_at,
                    resolved_at = excluded.resolved_at
                """,
                (
                    decision.decision_id,
                    decision.candidate_run_id,
                    decision.candidate_model_id,
                    decision.target_stage,
                    json.dumps(payload["policy_checks"], ensure_ascii=False),
                    json.dumps(payload["approvals"], ensure_ascii=False),
                    decision.chain_state,
                    decision.rollback_plan_ref,
                    decision.created_at.isoformat(),
                    decision.resolved_at.isoformat() if decision.resolved_at is not None else None,
                ),
            )
            conn.commit()

    def get(self, decision_id: str) -> PromotionDecision | None:
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT *
                FROM promotion_decisions
                WHERE decision_id = ?
                """,
                (decision_id,),
            ).fetchone()
        return self._row_to_decision(row) if row is not None else None

    def list_for_model(
        self,
        candidate_model_id: str,
        *,
        limit: int = 20,
    ) -> list[PromotionDecision]:
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM promotion_decisions
                WHERE candidate_model_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (candidate_model_id, limit),
            ).fetchall()
        return [self._row_to_decision(row) for row in rows]

    def _initialize(self) -> None:
        with self._lock, closing(self._connect()) as conn:
            version = self._schema_version(conn)
            if version < 1:
                conn.executescript(_MIGRATION_V1_SQL)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

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

    @staticmethod
    def _row_to_decision(row: sqlite3.Row) -> PromotionDecision:
        return PromotionDecision.model_validate(
            {
                "decision_id": str(row["decision_id"]),
                "candidate_run_id": str(row["candidate_run_id"]),
                "candidate_model_id": str(row["candidate_model_id"]),
                "target_stage": str(row["target_stage"]),
                "policy_checks": json.loads(str(row["policy_checks_json"] or "[]")),
                "approvals": json.loads(str(row["approvals_json"] or "[]")),
                "chain_state": str(row["chain_state"]),
                "rollback_plan_ref": str(row["rollback_plan_ref"]),
                "created_at": str(row["created_at"]),
                "resolved_at": str(row["resolved_at"]) if row["resolved_at"] is not None else None,
            }
        )


def _default_db_path(workspace_dir: str | None) -> Path:
    if workspace_dir is not None:
        return Path(workspace_dir) / "data" / "memory" / "decision_os" / "promotion_gate.db"
    return Path("data") / "memory" / "decision_os" / "promotion_gate.db"
