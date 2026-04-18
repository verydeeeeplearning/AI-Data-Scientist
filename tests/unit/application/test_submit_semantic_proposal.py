from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ds_agent.memory.semantic.application.submit_semantic_proposal import (
    SubmitSemanticProposalUseCase,
)
from ds_agent.memory.semantic.domain.proposal import SemanticProposal


class _ProposalRepo:
    def __init__(self) -> None:
        self.items: dict[str, SemanticProposal] = {}

    def get(self, proposal_id: str) -> SemanticProposal | None:
        return self.items.get(proposal_id)

    def list_pending(self, *, limit: int = 50) -> list[SemanticProposal]:
        return list(self.items.values())[:limit]

    def list_for_target(self, target_id: str) -> list[SemanticProposal]:
        return [item for item in self.items.values() if item.target_id == target_id]

    def save(self, proposal: SemanticProposal) -> None:
        self.items[proposal.proposal_id] = proposal

    def update(self, proposal: SemanticProposal) -> None:
        self.items[proposal.proposal_id] = proposal


@dataclass
class _Clock:
    now_value: datetime = datetime(2026, 4, 16, tzinfo=UTC)

    def now(self) -> datetime:
        return self.now_value


@dataclass
class _Ids:
    index: int = 0

    def new_task_id(self, now: datetime) -> str:
        return "TC-unused"

    def new_artifact_id(self, prefix: str) -> str:
        self.index += 1
        return f"{prefix}-{self.index}"


def test_submit_semantic_proposal_deduplicates_pending_target() -> None:
    repo = _ProposalRepo()
    use_case = SubmitSemanticProposalUseCase(repo, _Clock(), _Ids())

    first = use_case.execute(
        proposal_type="glossary_term",
        summary="Add MAU alias",
        payload={"term_id": "term.mau"},
        target_id="term.mau",
    )
    second = use_case.execute(
        proposal_type="glossary_term",
        summary="Add MAU alias",
        payload={"term_id": "term.mau"},
        target_id="term.mau",
    )

    assert first.created is True
    assert second.created is False
    assert second.deduplicated is True
    assert len(repo.items) == 1

