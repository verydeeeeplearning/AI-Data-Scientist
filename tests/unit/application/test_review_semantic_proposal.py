from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ds_agent.memory.semantic.application.review_semantic_proposal import (
    ReviewSemanticProposalUseCase,
)
from ds_agent.memory.semantic.domain.proposal import (
    SemanticProposal,
    SemanticProposalStatus,
    SemanticProposalType,
)


class _ProposalRepo:
    def __init__(self, proposal: SemanticProposal) -> None:
        self.item = proposal

    def get(self, proposal_id: str) -> SemanticProposal | None:
        return self.item if self.item.proposal_id == proposal_id else None

    def list_pending(self, *, limit: int = 50) -> list[SemanticProposal]:
        return [self.item]

    def list_for_target(self, target_id: str) -> list[SemanticProposal]:
        return [self.item] if self.item.target_id == target_id else []

    def save(self, proposal: SemanticProposal) -> None:
        self.item = proposal

    def update(self, proposal: SemanticProposal) -> None:
        self.item = proposal


@dataclass
class _Clock:
    now_value: datetime = datetime(2026, 4, 16, tzinfo=UTC)

    def now(self) -> datetime:
        return self.now_value


def _proposal() -> SemanticProposal:
    return SemanticProposal(
        proposal_id="SP-1",
        proposal_type=SemanticProposalType.GLOSSARY_TERM,
        summary="Add MAU alias",
        target_id="term.mau",
        payload={"term_id": "term.mau"},
        created_at=datetime(2026, 4, 16, tzinfo=UTC),
    )


def test_review_semantic_proposal_approves_pending_proposal() -> None:
    repo = _ProposalRepo(_proposal())
    result = ReviewSemanticProposalUseCase(repo, _Clock()).execute(
        "SP-1",
        action="approve",
        reviewer="reviewer@corp.example",
    )

    assert result.proposal.status is SemanticProposalStatus.APPROVED


def test_review_semantic_proposal_rejects_pending_proposal() -> None:
    repo = _ProposalRepo(_proposal())
    result = ReviewSemanticProposalUseCase(repo, _Clock()).execute(
        "SP-1",
        action="reject",
        reviewer="reviewer@corp.example",
    )

    assert result.proposal.status is SemanticProposalStatus.REJECTED

