"""Use case for reviewing semantic proposals."""

from __future__ import annotations

from typing import Literal

from ds_agent.application.ports.task_contract_support import Clock
from ds_agent.memory.semantic.application.dtos import ProposalSubmissionResultDTO
from ds_agent.memory.semantic.application.ports import SemanticProposalRepository
from ds_agent.memory.semantic.domain.proposal import SemanticProposalStatus


class ReviewSemanticProposalUseCase:
    """Approve or reject semantic proposals."""

    def __init__(
        self,
        proposals: SemanticProposalRepository,
        clock: Clock,
    ) -> None:
        self._proposals = proposals
        self._clock = clock

    def execute(
        self,
        proposal_id: str,
        *,
        action: Literal["approve", "reject"],
        reviewer: str,
    ) -> ProposalSubmissionResultDTO:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"proposal not found: {proposal_id}")

        target_status = (
            SemanticProposalStatus.APPROVED
            if action == "approve"
            else SemanticProposalStatus.REJECTED
        )
        updated = proposal.transition_to(
            target_status,
            reviewed_by=reviewer,
            reviewed_at=self._clock.now(),
        )
        self._proposals.update(updated)
        return ProposalSubmissionResultDTO(proposal=updated, created=False)

