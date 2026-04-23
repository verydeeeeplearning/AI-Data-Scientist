"""Runtime helpers that bridge semantic proposals into the approval bus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from ds_agent.domain.entities.approval import ApprovalRequest, ApprovalStatus
from ds_agent.infrastructure.semantic_memory_container import build_semantic_memory_container
from ds_agent.infrastructure.semantic_memory_runtime import resolve_semantic_db_path
from ds_agent.memory.semantic.domain.proposal import SemanticProposal


class ApprovalStoreLike(Protocol):
    def create(self, **kwargs: object) -> ApprovalRequest: ...


@dataclass(frozen=True)
class SemanticProposalApprovalOutcome:
    """Result of resolving a semantic-proposal approval."""

    proposal_id: str
    proposal_status: str
    action: str
    applied: bool
    applied_target: str | None = None


def create_semantic_proposal_approval(
    *,
    approval_store: ApprovalStoreLike,
    proposal: SemanticProposal,
    session_id: str,
    run_id: str | None,
    surface: str,
) -> ApprovalRequest:
    """Create an approval entry for one semantic proposal."""

    approval = approval_store.create(
        session_id=session_id,
        run_id=run_id,
        surface=surface,
        question=(
            "Review semantic proposal "
            f"[{proposal.proposal_type.value}] {proposal.summary}"
        ),
        kind="semantic_proposal",
        metadata={
            "proposalId": proposal.proposal_id,
            "proposalType": proposal.proposal_type.value,
            "targetId": proposal.target_id,
            "summary": proposal.summary,
            "risk": proposal.risk,
            "confidence": proposal.confidence,
            "autoApplyEligible": proposal.auto_apply_eligible,
        },
        options=["approve", "apply"],
        default="approve",
    )
    return cast(ApprovalRequest, approval)


def resolve_semantic_proposal_approval(
    approval: ApprovalRequest,
    *,
    workspace_dir: str | None,
    reviewer: str,
) -> SemanticProposalApprovalOutcome:
    """Review or apply the semantic proposal referenced by an approval."""

    proposal_id = _proposal_id_from_metadata(approval.metadata)
    container = build_semantic_memory_container(
        workspace_dir=workspace_dir,
        db_path=str(resolve_semantic_db_path(workspace_dir)),
    )

    if approval.status == ApprovalStatus.REJECTED:
        reviewed = container.review_semantic_proposal.execute(
            proposal_id,
            action="reject",
            reviewer=reviewer,
        )
        return SemanticProposalApprovalOutcome(
            proposal_id=proposal_id,
            proposal_status=reviewed.proposal.status.value,
            action="reject",
            applied=False,
        )

    reviewed = container.review_semantic_proposal.execute(
        proposal_id,
        action="approve",
        reviewer=reviewer,
    )
    if approval.response != "apply":
        return SemanticProposalApprovalOutcome(
            proposal_id=proposal_id,
            proposal_status=reviewed.proposal.status.value,
            action="approve",
            applied=False,
        )

    applied = container.apply_semantic_proposal.execute(proposal_id, reviewer=reviewer)
    return SemanticProposalApprovalOutcome(
        proposal_id=proposal_id,
        proposal_status=applied.proposal.status.value,
        action="apply",
        applied=True,
        applied_target=applied.applied_target,
    )


def _proposal_id_from_metadata(metadata: dict[str, object]) -> str:
    proposal_id = metadata.get("proposalId")
    if not isinstance(proposal_id, str) or not proposal_id.strip():
        raise ValueError("semantic proposal approval metadata requires proposalId")
    return proposal_id.strip()
