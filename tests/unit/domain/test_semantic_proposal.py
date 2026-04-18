from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ds_agent.memory.semantic.domain.proposal import (
    SemanticProposal,
    SemanticProposalStatus,
    SemanticProposalType,
)


def _proposal(auto_apply_eligible: bool = False) -> SemanticProposal:
    return SemanticProposal(
        proposal_id="proposal-1",
        proposal_type=SemanticProposalType.VERIFIED_QUERY,
        summary="Promote verified churn query",
        payload={"vq_id": "vq_churn_001"},
        confidence=0.92,
        risk="medium",
        auto_apply_eligible=auto_apply_eligible,
        created_at=datetime(2026, 4, 16, tzinfo=UTC),
    )


def test_pending_proposal_can_be_approved() -> None:
    approved = _proposal().transition_to(
        SemanticProposalStatus.APPROVED,
        reviewed_by="reviewer@corp.example",
        reviewed_at=datetime(2026, 4, 16, 1, tzinfo=UTC),
    )

    assert approved.status is SemanticProposalStatus.APPROVED
    assert approved.reviewed_by == "reviewer@corp.example"


def test_pending_proposal_cannot_auto_apply_without_eligibility() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        _proposal().transition_to(
            SemanticProposalStatus.APPLIED,
            reviewed_by="reviewer@corp.example",
            reviewed_at=datetime(2026, 4, 16, 1, tzinfo=UTC),
        )


def test_reviewed_status_requires_review_metadata() -> None:
    with pytest.raises(ValidationError, match="review metadata"):
        SemanticProposal(
            proposal_id="proposal-2",
            proposal_type=SemanticProposalType.GLOSSARY_TERM,
            status=SemanticProposalStatus.APPROVED,
            summary="Add glossary term",
            created_at=datetime(2026, 4, 16, tzinfo=UTC),
        )

