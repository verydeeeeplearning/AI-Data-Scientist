"""Tests for Telegram semantic proposal command handling."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ds_agent.memory.semantic.domain.proposal import (
    SemanticProposal,
    SemanticProposalStatus,
    SemanticProposalType,
)


def _make_proposal(
    *,
    proposal_id: str = "SP-001",
    proposal_type: SemanticProposalType = SemanticProposalType.GLOSSARY_TERM,
    status: SemanticProposalStatus = SemanticProposalStatus.PENDING,
    summary: str = "Add glossary term: MAU",
    target_id: str | None = "GLO-mau",
    confidence: float = 0.85,
    reviewed_by: str | None = None,
    reviewed_at: datetime | None = None,
) -> SemanticProposal:
    return SemanticProposal(
        proposal_id=proposal_id,
        proposal_type=proposal_type,
        status=status,
        summary=summary,
        target_id=target_id,
        payload={"canonical_form": "Monthly Active Users", "definition": "Users active in 30d"},
        evidence_refs=["run-001"],
        confidence=confidence,
        risk="low",
        proposed_by="agent",
        created_at=datetime(2026, 4, 16, 10, 0, tzinfo=UTC),
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
    )


def test_format_semantic_proposal_list_pending() -> None:
    """Format a list of pending proposals for Telegram display."""
    from ds_agent.gateway.telegram_semantic import format_proposal_list

    proposals = [
        _make_proposal(proposal_id="SP-001", summary="Add glossary: MAU"),
        _make_proposal(
            proposal_id="SP-002",
            summary="Add negative knowledge: do not join user_events with sessions",
            proposal_type=SemanticProposalType.NEGATIVE_KNOWLEDGE,
        ),
    ]
    text = format_proposal_list(proposals)
    assert "SP-001" in text
    assert "SP-002" in text
    assert "MAU" in text
    assert "pending" in text.lower()


def test_format_semantic_proposal_list_empty() -> None:
    """Empty proposal list shows a no-pending message."""
    from ds_agent.gateway.telegram_semantic import format_proposal_list

    text = format_proposal_list([])
    assert "no pending" in text.lower()


def test_format_semantic_proposal_detail() -> None:
    """Format a single proposal for detail display."""
    from ds_agent.gateway.telegram_semantic import format_proposal_detail

    proposal = _make_proposal()
    text = format_proposal_detail(proposal)
    assert "SP-001" in text
    assert "glossary_term" in text.lower()
    assert "MAU" in text
    assert "0.85" in text


def test_review_proposal_approve() -> None:
    """Approve transitions proposal to APPROVED."""
    proposal = _make_proposal()
    now = datetime(2026, 4, 16, 11, 0, tzinfo=UTC)
    approved = proposal.transition_to(
        SemanticProposalStatus.APPROVED,
        reviewed_by="operator",
        reviewed_at=now,
    )
    assert approved.status == SemanticProposalStatus.APPROVED
    assert approved.reviewed_by == "operator"


def test_review_proposal_reject() -> None:
    """Reject transitions proposal to REJECTED."""
    proposal = _make_proposal()
    now = datetime(2026, 4, 16, 11, 0, tzinfo=UTC)
    rejected = proposal.transition_to(
        SemanticProposalStatus.REJECTED,
        reviewed_by="operator",
        reviewed_at=now,
    )
    assert rejected.status == SemanticProposalStatus.REJECTED


def test_review_already_approved_cannot_reject() -> None:
    """An approved proposal cannot be rejected."""
    now = datetime(2026, 4, 16, 11, 0, tzinfo=UTC)
    approved = _make_proposal(
        status=SemanticProposalStatus.APPROVED,
        reviewed_by="operator",
        reviewed_at=now,
    )
    with pytest.raises(ValueError, match="not allowed"):
        approved.transition_to(
            SemanticProposalStatus.REJECTED,
            reviewed_by="operator",
            reviewed_at=now,
        )


def test_format_proposal_diff_preview() -> None:
    """Diff preview shows payload content."""
    from ds_agent.gateway.telegram_semantic import format_proposal_diff

    proposal = _make_proposal()
    diff_text = format_proposal_diff(proposal)
    assert "canonical_form" in diff_text
    assert "Monthly Active Users" in diff_text
