from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ds_agent.memory.semantic.domain.proposal import (
    SemanticProposal,
    SemanticProposalStatus,
    SemanticProposalType,
)
from ds_agent.memory.semantic.infrastructure.sqlite_base import SemanticSqliteDatabase
from ds_agent.memory.semantic.infrastructure.sqlite_proposal_repo import (
    SqliteSemanticProposalRepository,
)


def _db() -> SemanticSqliteDatabase:
    base_dir = Path("semantic_test_artifacts/proposal")
    base_dir.mkdir(parents=True, exist_ok=True)
    return SemanticSqliteDatabase(base_dir / f"{uuid.uuid4().hex}.db")


def test_proposal_repo_round_trip_and_status_update() -> None:
    repo = SqliteSemanticProposalRepository(_db())
    proposal = SemanticProposal(
        proposal_id="proposal-1",
        proposal_type=SemanticProposalType.GLOSSARY_TERM,
        summary="Add MAU alias",
        target_id="term.mau",
        payload={"term_id": "term.mau"},
        evidence_refs=["artifact://run/1", "decision://DL-1"],
        confidence=0.8,
        risk="low",
        auto_apply_eligible=True,
        created_at=datetime(2026, 4, 16, tzinfo=UTC),
    )
    repo.save(proposal)
    updated = proposal.transition_to(
        SemanticProposalStatus.APPLIED,
        reviewed_by="operator@corp.example",
        reviewed_at=datetime(2026, 4, 16, 1, tzinfo=UTC),
    )
    repo.update(updated)

    restored = repo.get("proposal-1")
    assert restored is not None
    assert restored.status is SemanticProposalStatus.APPLIED
    assert restored.evidence_refs == ["artifact://run/1", "decision://DL-1"]

    assert repo.list_pending() == []
    assert [item.proposal_id for item in repo.list_for_target("term.mau")] == ["proposal-1"]
