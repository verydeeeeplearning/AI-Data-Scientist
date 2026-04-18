"""Use case for capturing failure lessons as pending semantic proposals."""

from __future__ import annotations

from ds_agent.application.ports.task_contract_support import Clock
from ds_agent.memory.semantic.application.dtos import ProposalSubmissionResultDTO
from ds_agent.memory.semantic.application.submit_semantic_proposal import (
    SubmitSemanticProposalUseCase,
)
from ds_agent.memory.semantic.domain.proposal import SemanticProposalType


class RecordNegativeKnowledgeUseCase:
    """Convert a failure lesson into a pending negative-knowledge proposal."""

    def __init__(
        self,
        submit_proposal: SubmitSemanticProposalUseCase,
        clock: Clock,
    ) -> None:
        self._submit_proposal = submit_proposal
        self._clock = clock

    def execute(
        self,
        *,
        topic: str,
        wrong_approach: str,
        why_wrong: str,
        correct_approach: str,
        references: list[str] | None = None,
        source_run_id: str | None = None,
        source_session_id: str | None = None,
    ) -> ProposalSubmissionResultDTO:
        payload = {
            "nk_id": f"nk::{topic}::{correct_approach}",
            "topic": topic,
            "wrong_approach": wrong_approach,
            "why_wrong": why_wrong,
            "correct_approach": correct_approach,
            "recorded_at": self._clock.now().isoformat(),
            "recorded_by": "retrospective",
            "references": references or [],
        }
        return self._submit_proposal.execute(
            proposal_type=SemanticProposalType.NEGATIVE_KNOWLEDGE,
            summary=f"Negative knowledge for {topic}",
            payload=payload,
            target_id=topic,
            evidence_refs=references or [],
            confidence=0.8,
            risk="high",
            source_run_id=source_run_id,
            source_session_id=source_session_id,
        )
