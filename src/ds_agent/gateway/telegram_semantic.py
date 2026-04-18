"""Telegram formatting helpers for semantic proposal review."""

from __future__ import annotations

import json
from collections.abc import Sequence

from ds_agent.memory.semantic.domain.proposal import SemanticProposal


def format_proposal_list(proposals: Sequence[SemanticProposal]) -> str:
    """Format a list of proposals for Telegram display."""
    if not proposals:
        return "No pending semantic proposals."

    lines = [f"Semantic proposals ({len(proposals)} pending):\n"]
    for p in proposals:
        risk_icon = {"low": "", "medium": "", "high": ""}.get(p.risk, "")
        lines.append(
            f"  {risk_icon} {p.proposal_id}  "
            f"{p.proposal_type.value}  "
            f"conf={p.confidence:.2f}  "
            f"{p.status.value}\n"
            f"      {p.summary}",
        )
    return "\n".join(lines)


def format_proposal_detail(proposal: SemanticProposal) -> str:
    """Format one proposal for detail display."""
    lines = [
        f"Proposal {proposal.proposal_id}",
        f"  Type: {proposal.proposal_type.value}",
        f"  Status: {proposal.status.value}",
        f"  Target: {proposal.target_id or '-'}",
        f"  Summary: {proposal.summary}",
        f"  Confidence: {proposal.confidence:.2f}",
        f"  Risk: {proposal.risk}",
        f"  Proposed by: {proposal.proposed_by}",
        f"  Created: {proposal.created_at.isoformat()}",
    ]
    if proposal.reviewed_by:
        lines.append(f"  Reviewed by: {proposal.reviewed_by}")
    if proposal.reviewed_at:
        lines.append(f"  Reviewed at: {proposal.reviewed_at.isoformat()}")
    if proposal.evidence_refs:
        lines.append(f"  Evidence: {', '.join(proposal.evidence_refs)}")
    return "\n".join(lines)


def format_proposal_diff(proposal: SemanticProposal) -> str:
    """Format the payload as a diff preview."""
    if not proposal.payload:
        return f"Proposal {proposal.proposal_id}: (no payload)"

    lines = [f"Diff for {proposal.proposal_id} ({proposal.proposal_type.value}):"]
    for key, value in proposal.payload.items():
        if isinstance(value, (dict, list)):
            formatted = json.dumps(value, ensure_ascii=False, indent=2)
            lines.append(f"  + {key}:\n{formatted}")
        else:
            lines.append(f"  + {key}: {value}")
    return "\n".join(lines)
