"""SQLite repository for semantic write-back proposals."""

from __future__ import annotations

import sqlite3

from ds_agent.memory.semantic.domain.proposal import SemanticProposal
from ds_agent.memory.semantic.infrastructure.sqlite_base import (
    SemanticSqliteDatabase,
    json_dumps,
    json_loads,
)


class SqliteSemanticProposalRepository:
    """SQLite-backed proposal queue repository."""

    def __init__(self, db: SemanticSqliteDatabase) -> None:
        self._db = db

    def get(self, proposal_id: str) -> SemanticProposal | None:
        with self._db.lock, self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM semantic_proposal WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            evidence_rows = conn.execute(
                """
                SELECT evidence_ref
                FROM semantic_proposal_evidence
                WHERE proposal_id = ?
                ORDER BY evidence_id
                """,
                (proposal_id,),
            ).fetchall()
        return self._row_to_proposal(row, evidence_rows) if row is not None else None

    def list_pending(self, *, limit: int = 50) -> list[SemanticProposal]:
        with self._db.lock, self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM semantic_proposal
                WHERE status = 'pending'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        proposal_ids = [str(row["proposal_id"]) for row in rows]
        proposals: list[SemanticProposal] = []
        for proposal_id in proposal_ids:
            proposal = self.get(proposal_id)
            if proposal is not None:
                proposals.append(proposal)
        return proposals

    def list_for_target(self, target_id: str) -> list[SemanticProposal]:
        with self._db.lock, self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM semantic_proposal
                WHERE target_id = ?
                ORDER BY created_at DESC
                """,
                (target_id,),
            ).fetchall()
        proposal_ids = [str(row["proposal_id"]) for row in rows]
        proposals: list[SemanticProposal] = []
        for proposal_id in proposal_ids:
            proposal = self.get(proposal_id)
            if proposal is not None:
                proposals.append(proposal)
        return proposals

    def save(self, proposal: SemanticProposal) -> None:
        self._upsert(proposal)

    def update(self, proposal: SemanticProposal) -> None:
        self._upsert(proposal)

    def _upsert(self, proposal: SemanticProposal) -> None:
        with self._db.lock, self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO semantic_proposal (
                    proposal_id, proposal_type, status, source_run_id, source_session_id,
                    source_tool_name, target_id, summary, payload_json, confidence, risk,
                    proposed_by, auto_apply_eligible, created_at, expires_at,
                    reviewed_by, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.proposal_id,
                    proposal.proposal_type.value,
                    proposal.status.value,
                    proposal.source_run_id,
                    proposal.source_session_id,
                    proposal.source_tool_name,
                    proposal.target_id,
                    proposal.summary,
                    json_dumps(proposal.payload),
                    proposal.confidence,
                    proposal.risk,
                    proposal.proposed_by,
                    1 if proposal.auto_apply_eligible else 0,
                    proposal.created_at.isoformat(),
                    proposal.expires_at.isoformat() if proposal.expires_at is not None else None,
                    proposal.reviewed_by,
                    proposal.reviewed_at.isoformat() if proposal.reviewed_at is not None else None,
                ),
            )
            existing_refs = {
                str(row["evidence_ref"])
                for row in conn.execute(
                    """
                    SELECT evidence_ref
                    FROM semantic_proposal_evidence
                    WHERE proposal_id = ?
                    """,
                    (proposal.proposal_id,),
                ).fetchall()
            }
            new_refs = [ref for ref in proposal.evidence_refs if ref not in existing_refs]
            conn.executemany(
                """
                INSERT INTO semantic_proposal_evidence (
                    proposal_id, evidence_type, evidence_ref, note
                )
                VALUES (?, ?, ?, ?)
                """,
                [(proposal.proposal_id, "reference", ref, None) for ref in new_refs],
            )
            conn.commit()

    @staticmethod
    def _row_to_proposal(
        row: sqlite3.Row,
        evidence_rows: list[sqlite3.Row],
    ) -> SemanticProposal:
        evidence_refs = [str(evidence_row["evidence_ref"]) for evidence_row in evidence_rows]
        return SemanticProposal.model_validate(
            {
                "proposal_id": str(row["proposal_id"]),
                "proposal_type": row["proposal_type"],
                "status": row["status"],
                "source_run_id": (
                    str(row["source_run_id"]) if row["source_run_id"] is not None else None
                ),
                "source_session_id": (
                    str(row["source_session_id"]) if row["source_session_id"] is not None else None
                ),
                "source_tool_name": (
                    str(row["source_tool_name"]) if row["source_tool_name"] is not None else None
                ),
                "target_id": str(row["target_id"]) if row["target_id"] is not None else None,
                "summary": str(row["summary"]),
                "payload": json_loads(row["payload_json"], default={}),
                "evidence_refs": evidence_refs,
                "confidence": float(row["confidence"]),
                "risk": row["risk"],
                "proposed_by": row["proposed_by"],
                "auto_apply_eligible": bool(row["auto_apply_eligible"]),
                "created_at": str(row["created_at"]),
                "expires_at": str(row["expires_at"]) if row["expires_at"] is not None else None,
                "reviewed_by": str(row["reviewed_by"]) if row["reviewed_by"] is not None else None,
                "reviewed_at": str(row["reviewed_at"]) if row["reviewed_at"] is not None else None,
            }
        )
