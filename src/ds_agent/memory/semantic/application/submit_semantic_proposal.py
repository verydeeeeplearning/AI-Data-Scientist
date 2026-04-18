"""Use case for creating semantic proposals."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from ds_agent.application.ports.task_contract_support import Clock, IdGenerator
from ds_agent.memory.semantic.application.dtos import ProposalSubmissionResultDTO
from ds_agent.memory.semantic.application.ports import SemanticProposalRepository
from ds_agent.memory.semantic.domain.proposal import (
    SemanticProposal,
    SemanticProposalStatus,
    SemanticProposalType,
)


class SubmitSemanticProposalUseCase:
    """Create or deduplicate semantic proposals."""

    def __init__(
        self,
        proposals: SemanticProposalRepository,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._proposals = proposals
        self._clock = clock
        self._ids = ids

    def execute(
        self,
        *,
        proposal_type: SemanticProposalType | str,
        summary: str,
        payload: dict[str, Any],
        target_id: str | None = None,
        evidence_refs: list[str] | None = None,
        confidence: float = 0.0,
        risk: Literal["low", "medium", "high"] = "medium",
        proposed_by: Literal["agent", "human", "adapter_sync"] = "agent",
        auto_apply_eligible: bool = False,
        source_run_id: str | None = None,
        source_session_id: str | None = None,
        source_tool_name: str | None = None,
        expires_at: datetime | None = None,
    ) -> ProposalSubmissionResultDTO:
        proposal_kind = SemanticProposalType(proposal_type)
        if target_id is not None:
            for existing in self._proposals.list_for_target(target_id):
                if (
                    existing.status == SemanticProposalStatus.PENDING
                    and existing.proposal_type == proposal_kind
                    and existing.payload == payload
                ):
                    return ProposalSubmissionResultDTO(
                        proposal=existing,
                        created=False,
                        deduplicated=True,
                    )

        proposal = SemanticProposal(
            proposal_id=self._ids.new_artifact_id("SP"),
            proposal_type=proposal_kind,
            summary=summary,
            payload=payload,
            target_id=target_id,
            evidence_refs=evidence_refs or [],
            confidence=confidence,
            risk=risk,
            proposed_by=proposed_by,
            auto_apply_eligible=auto_apply_eligible,
            source_run_id=source_run_id,
            source_session_id=source_session_id,
            source_tool_name=source_tool_name,
            created_at=self._clock.now(),
            expires_at=expires_at,
        )
        self._proposals.save(proposal)
        return ProposalSubmissionResultDTO(proposal=proposal, created=True)
