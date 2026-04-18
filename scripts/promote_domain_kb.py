"""Promote existing domain_kb insights into semantic proposals.

Reads the JSON-based DomainKB profiles and creates SemanticProposal
entries for each insight, classified by category:
  - project_finding / failure_lesson → NEGATIVE_KNOWLEDGE
  - manual → GLOSSARY_TERM (if short definition-like) or NEGATIVE_KNOWLEDGE
  - general → NEGATIVE_KNOWLEDGE

Supports dry-run mode (default) that prints candidates without persisting.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from ds_agent.memory.domain_kb import DomainKB
from ds_agent.memory.semantic.application.ports import SemanticProposalRepository
from ds_agent.memory.semantic.domain.proposal import (
    SemanticProposal,
    SemanticProposalType,
)
from ds_agent.memory.semantic.infrastructure import (
    SemanticSqliteDatabase,
    SqliteSemanticProposalRepository,
)


def _classify_insight(insight: dict) -> SemanticProposalType:
    """Map a domain_kb insight category to a proposal type."""
    category = insight.get("category", "general")
    if category in {"failure_lesson", "project_finding"}:
        return SemanticProposalType.NEGATIVE_KNOWLEDGE
    if category == "manual":
        content = insight.get("content", "")
        if len(content) < 120 and ":" in content:
            return SemanticProposalType.GLOSSARY_TERM
        return SemanticProposalType.NEGATIVE_KNOWLEDGE
    return SemanticProposalType.NEGATIVE_KNOWLEDGE


def _build_proposal(
    domain: str,
    insight: dict,
    counter: int,
) -> SemanticProposal:
    """Build a SemanticProposal from one domain_kb insight."""
    proposal_type = _classify_insight(insight)
    content = insight.get("content", "")
    confidence = insight.get("confidence", 0.5)
    tags = insight.get("tags", [])
    return SemanticProposal(
        proposal_id=f"SP-promote-{counter:04d}",
        proposal_type=proposal_type,
        summary=content[:200],
        target_id=f"domain:{domain}",
        payload={
            "content": content,
            "source_domain": domain,
            "source_category": insight.get("category", "general"),
            "source_tags": tags,
        },
        evidence_refs=[f"domain_kb:{domain}"],
        confidence=min(confidence, 1.0),
        risk="low",
        proposed_by="adapter_sync",
        auto_apply_eligible=False,
        created_at=datetime.now(UTC),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Promote domain_kb insights to semantic proposals",
    )
    parser.add_argument(
        "--workspace-dir",
        default=".",
        help="Workspace directory containing the semantic DB",
    )
    parser.add_argument(
        "--domain-kb-dir",
        default="data/memory/domain_kb",
        help="Path to domain_kb data directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Print candidates without persisting (default)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Actually persist proposals to semantic DB",
    )
    parser.add_argument(
        "--domain",
        default=None,
        help="Filter to a specific domain (optional)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    dry_run = not args.apply

    kb = DomainKB(data_dir=args.domain_kb_dir)
    insights = kb.get_insights(domain=args.domain, limit=500)

    if not insights:
        print("No domain_kb insights found.")
        return

    repo: SemanticProposalRepository | None = None
    if not dry_run:
        db = SemanticSqliteDatabase(args.workspace_dir)
        repo = SqliteSemanticProposalRepository(db)

    proposals: list[SemanticProposal] = []
    for counter, insight in enumerate(insights, start=1):
        domain = insight.get("domain", "general")
        proposal = _build_proposal(domain, insight, counter)
        proposals.append(proposal)

    print(f"Found {len(proposals)} candidates from domain_kb:\n")
    for p in proposals:
        status = "[DRY-RUN]" if dry_run else "[PERSIST]"
        print(
            f"  {status} {p.proposal_id}  "
            f"{p.proposal_type.value:20s}  "
            f"conf={p.confidence:.2f}  "
            f"{p.summary[:60]}",
        )

    if not dry_run and repo is not None:
        for p in proposals:
            repo.save(p)
        print(f"\nPersisted {len(proposals)} proposals to semantic DB.")
    else:
        print(f"\nDry-run complete. Use --apply to persist {len(proposals)} proposals.")


if __name__ == "__main__":
    main()
