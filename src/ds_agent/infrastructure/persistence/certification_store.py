"""SQLite-backed store for autonomy certification evidence and approvals."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, date, datetime
from pathlib import Path

from ds_agent.domain.entities.certification import (
    AutonomyRunStat,
    CertificationRecord,
    CertificationStats,
    certification_rank,
)
from ds_agent.domain.value_objects.authority_mode import AuthorityMode
from ds_agent.runtime.transcript_store import get_runtime_storage_root

_MIGRATION_V1_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS autonomy_certification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_name TEXT NOT NULL,
    mission_version INTEGER NOT NULL,
    level TEXT NOT NULL,
    transition_from TEXT,
    approved_by_json TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    evidence_ref TEXT,
    next_review TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cert_unique
ON autonomy_certification(mission_name, mission_version, level, approved_at);

CREATE INDEX IF NOT EXISTS idx_cert_mission
ON autonomy_certification(mission_name, mission_version, approved_at DESC);

CREATE TABLE IF NOT EXISTS autonomy_run_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_name TEXT NOT NULL,
    mission_version INTEGER NOT NULL,
    run_id TEXT NOT NULL UNIQUE,
    authority TEXT NOT NULL,
    audience TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    outcome TEXT,
    verifier_score REAL,
    violations_critical INTEGER NOT NULL DEFAULT 0,
    violations_warn INTEGER NOT NULL DEFAULT 0,
    rollback_rehearsal INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_run_stats_mission
ON autonomy_run_stats(mission_name, mission_version, started_at DESC);

INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (1, datetime('now'));
"""


class SqliteCertificationStore:
    """SQLite implementation of autonomy certification persistence."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    @classmethod
    def for_workspace(cls, workspace_dir: str | None = None) -> SqliteCertificationStore:
        """Create a store at the default runtime location for a workspace."""

        return cls(get_runtime_storage_root(workspace_dir) / "autonomy_control_plane.db")

    def save_certification(self, record: CertificationRecord) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO autonomy_certification (
                    mission_name,
                    mission_version,
                    level,
                    transition_from,
                    approved_by_json,
                    approved_at,
                    evidence_ref,
                    next_review
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.mission_name,
                    record.mission_version,
                    record.level.value,
                    record.transition_from.value if record.transition_from is not None else None,
                    json.dumps(list(record.approved_by), ensure_ascii=False),
                    record.approved_at.isoformat(),
                    record.evidence_ref,
                    record.next_review.isoformat() if record.next_review is not None else None,
                ),
            )
            conn.commit()

    def latest_certification(
        self,
        mission_name: str,
        *,
        mission_version: int | None = None,
    ) -> CertificationRecord | None:
        params: list[object] = [mission_name]
        where = "mission_name = ?"
        if mission_version is not None:
            where += " AND mission_version = ?"
            params.append(mission_version)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT *
                FROM autonomy_certification
                WHERE {where}
                ORDER BY approved_at DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
        if row is None:
            return None
        return self._deserialize_record(row)

    def list_certifications(
        self,
        mission_name: str,
        *,
        mission_version: int | None = None,
        limit: int = 20,
    ) -> list[CertificationRecord]:
        params: list[object] = [mission_name]
        where = "mission_name = ?"
        if mission_version is not None:
            where += " AND mission_version = ?"
            params.append(mission_version)
        params.append(limit)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM autonomy_certification
                WHERE {where}
                ORDER BY approved_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._deserialize_record(row) for row in rows]

    def is_certified(
        self,
        mission_name: str,
        level: AuthorityMode | str,
        *,
        mission_version: int | None = None,
    ) -> bool:
        latest = self.latest_certification(mission_name, mission_version=mission_version)
        if latest is None:
            return False
        return certification_rank(latest.level) >= certification_rank(level)

    def record_run_stat(self, stat: AutonomyRunStat) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO autonomy_run_stats (
                    mission_name,
                    mission_version,
                    run_id,
                    authority,
                    audience,
                    started_at,
                    ended_at,
                    outcome,
                    verifier_score,
                    violations_critical,
                    violations_warn,
                    rollback_rehearsal
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    mission_name = excluded.mission_name,
                    mission_version = excluded.mission_version,
                    authority = excluded.authority,
                    audience = excluded.audience,
                    started_at = excluded.started_at,
                    ended_at = excluded.ended_at,
                    outcome = excluded.outcome,
                    verifier_score = excluded.verifier_score,
                    violations_critical = excluded.violations_critical,
                    violations_warn = excluded.violations_warn,
                    rollback_rehearsal = excluded.rollback_rehearsal
                """,
                (
                    stat.mission_name,
                    stat.mission_version,
                    stat.run_id,
                    stat.authority.value,
                    stat.audience.value,
                    stat.started_at.isoformat(),
                    stat.ended_at.isoformat() if stat.ended_at is not None else None,
                    stat.outcome,
                    stat.verifier_score,
                    stat.violations_critical,
                    stat.violations_warn,
                    int(stat.rollback_rehearsal),
                ),
            )
            conn.commit()

    def stats_for(
        self,
        mission_name: str,
        *,
        mission_version: int | None = None,
    ) -> CertificationStats:
        params: list[object] = [mission_name]
        where = "mission_name = ?"
        if mission_version is not None:
            where += " AND mission_version = ?"
            params.append(mission_version)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT
                    COALESCE(
                        SUM(CASE WHEN authority = 'shadow' AND outcome = 'success' THEN 1 END),
                        0
                    ) AS shadow_runs_passed,
                    COALESCE(SUM(violations_critical), 0) AS critical_violations,
                    AVG(verifier_score) AS verifier_avg_score,
                    COALESCE(MAX(rollback_rehearsal), 0) AS rollback_rehearsal_passed
                FROM autonomy_run_stats
                WHERE {where}
                """,
                params,
            ).fetchone()
        if row is None:
            return CertificationStats()
        score = row["verifier_avg_score"]
        return CertificationStats(
            shadow_runs_passed=int(row["shadow_runs_passed"] or 0),
            critical_violations=int(row["critical_violations"] or 0),
            verifier_avg_score=(float(score) if score is not None else None),
            rollback_rehearsal_passed=bool(row["rollback_rehearsal_passed"]),
        )

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(_MIGRATION_V1_SQL)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _deserialize_record(row: sqlite3.Row) -> CertificationRecord:
        approved_by = json.loads(row["approved_by_json"])
        return CertificationRecord(
            mission_name=row["mission_name"],
            mission_version=int(row["mission_version"]),
            level=AuthorityMode(str(row["level"])),
            transition_from=(
                AuthorityMode(str(row["transition_from"]))
                if row["transition_from"] is not None
                else None
            ),
            approved_by=tuple(str(item) for item in approved_by),
            approved_at=_parse_datetime(str(row["approved_at"])),
            evidence_ref=str(row["evidence_ref"]) if row["evidence_ref"] is not None else None,
            next_review=_parse_date(str(row["next_review"])) if row["next_review"] else None,
        )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)
