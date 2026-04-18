from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ds_agent.memory.semantic.application.record_negative_knowledge import (
    RecordNegativeKnowledgeUseCase,
)
from ds_agent.memory.semantic.application.submit_semantic_proposal import (
    SubmitSemanticProposalUseCase,
)
from ds_agent.memory.semantic.domain.proposal import (
    SemanticProposal,
    SemanticProposalStatus,
)


class _ProposalRepo:
    def __init__(self) -> None:
        self.items: dict[str, SemanticProposal] = {}

    def get(self, proposal_id: str) -> SemanticProposal | None:
        return self.items.get(proposal_id)

    def list_pending(self, *, limit: int = 50) -> list[SemanticProposal]:
        return list(self.items.values())

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


def test_record_negative_knowledge_creates_pending_proposal() -> None:
    clock = _Clock()
    repo = _ProposalRepo()
    submit = SubmitSemanticProposalUseCase(repo, clock, _Ids())
    result = RecordNegativeKnowledgeUseCase(submit, clock).execute(
        topic="monthly_churn_rate",
        wrong_approach="included promo cohort",
        why_wrong="it biases the metric definition",
        correct_approach="exclude promo cohort from churn base",
        references=["DL-1"],
    )

    assert result.created is True
    assert result.proposal.status is SemanticProposalStatus.PENDING
    assert result.proposal.proposal_type.value == "negative_knowledge"
    assert result.proposal.payload["recorded_at"] == clock.now_value.isoformat()
