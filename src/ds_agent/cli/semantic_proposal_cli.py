"""Semantic proposal CLI helpers."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from rich.console import Console
from rich.table import Table

from ds_agent.domain.entities.approval import ApprovalRequest, ApprovalStatus
from ds_agent.infrastructure.semantic_memory_container import (
    SemanticMemoryContainer,
    build_semantic_memory_container,
)
from ds_agent.infrastructure.semantic_memory_runtime import resolve_semantic_db_path
from ds_agent.memory.semantic.domain.proposal import (
    SemanticProposal,
    SemanticProposalStatus,
    SemanticProposalType,
)
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.semantic_proposal_router import (
    SemanticProposalApprovalOutcome,
    resolve_semantic_proposal_approval,
)

_CLI_REVIEWER = "cli.operator"
_RECORD_SEARCH_MULTIPLIER = 20
_MIN_RECORD_SEARCH_LIMIT = 200
_APPROVAL_STATUS_CHOICES = [*(item.value for item in ApprovalStatus), "all"]
_PROPOSAL_RISKS = ("low", "medium", "high")

ProposalRisk = Literal["low", "medium", "high"]
SemanticProposalActionResult = tuple[
    SemanticProposal,
    ApprovalRequest | None,
    SemanticProposalApprovalOutcome,
]


@dataclass(frozen=True)
class SemanticProposalRecord:
    """Joined semantic proposal and approval state."""

    proposal: SemanticProposal | None
    approval: ApprovalRequest | None


@dataclass(frozen=True)
class SemanticProposalFilters:
    """CLI filters for semantic proposal selection."""

    approval_status: ApprovalStatus | None = ApprovalStatus.PENDING
    proposal_status: SemanticProposalStatus | None = None
    proposal_type: SemanticProposalType | None = None
    risk: ProposalRisk | None = None
    session_id: str | None = None


def run_semantic_proposal_command(
    argv: Sequence[str],
    *,
    console: Console,
    workspace_dir: str | None,
) -> int:
    """Run `ds-agent semantic proposal ...`."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) or ["list"])
    approval_store = JsonApprovalStore(workspace_dir)
    container = _build_runtime_container(workspace_dir)
    filters = _filters_from_args(args)

    if args.command == "list":
        records = _list_records(
            container=container,
            approval_store=approval_store,
            filters=filters,
            limit=args.limit,
        )
        console.print(_render_record_list(records, filters=filters))
        return 0

    if args.command == "show":
        record = _resolve_record(
            args.ref,
            container=container,
            approval_store=approval_store,
        )
        console.print(_render_record_detail(record))
        return 0

    if args.command in {"approve-many", "reject-many", "apply-many"}:
        records = _list_records(
            container=container,
            approval_store=approval_store,
            filters=filters,
            limit=args.limit,
        )
        results = _execute_batch_action(
            records,
            action=args.command.removesuffix("-many"),
            container=container,
            approval_store=approval_store,
            workspace_dir=workspace_dir,
            actor=args.actor or _CLI_REVIEWER,
            reason=getattr(args, "reason", None),
        )
        console.print(
            _render_batch_action_result(
                action=args.command.removesuffix("-many"),
                results=results,
                filters=filters,
            )
        )
        return 0

    record = _resolve_record(
        args.ref,
        container=container,
        approval_store=approval_store,
    )
    proposal, approval, outcome = _execute_action(
        record,
        action=args.command,
        container=container,
        approval_store=approval_store,
        workspace_dir=workspace_dir,
        actor=args.actor or _CLI_REVIEWER,
        reason=getattr(args, "reason", None),
    )
    console.print(
        _render_action_result(
            proposal=proposal,
            approval=approval,
            outcome=outcome,
        )
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ds-agent semantic proposal", add_help=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", add_help=False)
    _add_filter_arguments(
        list_parser,
        include_legacy_status_alias=True,
        default_approval_status=ApprovalStatus.PENDING.value,
    )

    show = subparsers.add_parser("show", add_help=False)
    show.add_argument("ref")

    approve = subparsers.add_parser("approve", add_help=False)
    approve.add_argument("ref")
    approve.add_argument("--actor")

    reject = subparsers.add_parser("reject", add_help=False)
    reject.add_argument("ref")
    reject.add_argument("--actor")
    reject.add_argument("--reason")

    apply = subparsers.add_parser("apply", add_help=False)
    apply.add_argument("ref")
    apply.add_argument("--actor")

    approve_many = subparsers.add_parser("approve-many", add_help=False)
    approve_many.add_argument("--actor")
    _add_filter_arguments(
        approve_many,
        include_legacy_status_alias=False,
        default_approval_status=ApprovalStatus.PENDING.value,
    )

    reject_many = subparsers.add_parser("reject-many", add_help=False)
    reject_many.add_argument("--actor")
    reject_many.add_argument("--reason")
    _add_filter_arguments(
        reject_many,
        include_legacy_status_alias=False,
        default_approval_status=ApprovalStatus.PENDING.value,
    )

    apply_many = subparsers.add_parser("apply-many", add_help=False)
    apply_many.add_argument("--actor")
    _add_filter_arguments(
        apply_many,
        include_legacy_status_alias=False,
        default_approval_status=ApprovalStatus.PENDING.value,
    )

    return parser


def _build_runtime_container(workspace_dir: str | None) -> SemanticMemoryContainer:
    return build_semantic_memory_container(
        workspace_dir=workspace_dir,
        db_path=str(resolve_semantic_db_path(workspace_dir)),
    )


def _add_filter_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_legacy_status_alias: bool,
    default_approval_status: str,
) -> None:
    option_strings = ["--approval-status"]
    if include_legacy_status_alias:
        option_strings.insert(0, "--status")
    parser.add_argument(
        *option_strings,
        choices=_APPROVAL_STATUS_CHOICES,
        default=default_approval_status,
    )
    parser.add_argument(
        "--proposal-status",
        choices=[item.value for item in SemanticProposalStatus],
        default=None,
    )
    parser.add_argument(
        "--proposal-type",
        choices=[item.value for item in SemanticProposalType],
        default=None,
    )
    parser.add_argument(
        "--risk",
        choices=list(_PROPOSAL_RISKS),
        default=None,
    )
    parser.add_argument("--session-id")
    parser.add_argument("--limit", type=int, default=20)


def _filters_from_args(args: argparse.Namespace) -> SemanticProposalFilters:
    approval_status_value = getattr(
        args,
        "approval_status",
        getattr(args, "status", ApprovalStatus.PENDING.value),
    )
    proposal_status_value = getattr(args, "proposal_status", None)
    proposal_type_value = getattr(args, "proposal_type", None)
    risk_value = getattr(args, "risk", None)
    return SemanticProposalFilters(
        approval_status=(
            None if approval_status_value == "all" else ApprovalStatus(approval_status_value)
        ),
        proposal_status=(
            SemanticProposalStatus(proposal_status_value)
            if proposal_status_value is not None
            else None
        ),
        proposal_type=(
            SemanticProposalType(proposal_type_value)
            if proposal_type_value is not None
            else None
        ),
        risk=risk_value,
        session_id=getattr(args, "session_id", None),
    )


def _list_records(
    *,
    container: SemanticMemoryContainer,
    approval_store: JsonApprovalStore,
    filters: SemanticProposalFilters,
    limit: int,
) -> list[SemanticProposalRecord]:
    records: list[SemanticProposalRecord] = []
    seen_ids: set[str] = set()
    search_limit = max(limit * _RECORD_SEARCH_MULTIPLIER, _MIN_RECORD_SEARCH_LIMIT)
    approval_index = _build_approval_index(
        approval_store,
        session_id=filters.session_id,
        status=filters.approval_status,
        limit=search_limit,
    )

    if _needs_pending_scan(filters):
        proposals = container.proposals.list_pending(limit=search_limit)
        if filters.session_id is not None:
            proposals = [
                proposal
                for proposal in proposals
                if proposal.source_session_id == filters.session_id
            ]
        for proposal in proposals:
            record = SemanticProposalRecord(
                proposal=proposal,
                approval=approval_index.get(proposal.proposal_id),
            )
            if not _matches_filters(record, filters):
                continue
            records.append(record)
            seen_ids.add(proposal.proposal_id)
            if len(records) >= limit:
                return records[:limit]

    if len(records) >= limit:
        return records[:limit]

    for proposal_id, approval in approval_index.items():
        if proposal_id in seen_ids:
            continue
        indexed_proposal = container.proposals.get(proposal_id)
        record = SemanticProposalRecord(
            proposal=indexed_proposal,
            approval=approval,
        )
        if not _matches_filters(record, filters):
            continue
        records.append(record)
        if indexed_proposal is not None:
            seen_ids.add(indexed_proposal.proposal_id)
        if len(records) >= limit:
            break
    return records[:limit]


def _needs_pending_scan(filters: SemanticProposalFilters) -> bool:
    if filters.proposal_status is SemanticProposalStatus.PENDING:
        return True
    return filters.approval_status in {None, ApprovalStatus.PENDING}


def _matches_filters(
    record: SemanticProposalRecord,
    filters: SemanticProposalFilters,
) -> bool:
    proposal = record.proposal
    approval = record.approval
    if filters.session_id is not None:
        proposal_session_id = proposal.source_session_id if proposal is not None else None
        approval_session_id = approval.session_id if approval is not None else None
        if filters.session_id not in {proposal_session_id, approval_session_id}:
            return False
    if filters.approval_status is not None:
        if approval is not None:
            if approval.status != filters.approval_status:
                return False
        elif filters.approval_status is not ApprovalStatus.PENDING:
            return False
    if filters.proposal_status is not None and (
        proposal is None or proposal.status != filters.proposal_status
    ):
        return False
    if filters.proposal_type is not None and (
        proposal is None or proposal.proposal_type != filters.proposal_type
    ):
        return False
    return filters.risk is None or (proposal is not None and proposal.risk == filters.risk)


def _build_approval_index(
    approval_store: JsonApprovalStore,
    *,
    session_id: str | None,
    status: ApprovalStatus | None,
    limit: int,
) -> dict[str, ApprovalRequest]:
    approvals = [
        approval
        for approval in approval_store.list(
            session_id=session_id,
            status=status,
            limit=limit,
        )
        if approval.kind == "semantic_proposal"
    ]
    index: dict[str, ApprovalRequest] = {}
    for approval in approvals:
        proposal_id = _proposal_id_from_metadata(approval.metadata)
        if proposal_id is None:
            continue
        index.setdefault(proposal_id, approval)
    return index


def _resolve_record(
    ref: str,
    *,
    container: SemanticMemoryContainer,
    approval_store: JsonApprovalStore,
) -> SemanticProposalRecord:
    approval = approval_store.get(ref)
    if approval is not None and approval.kind == "semantic_proposal":
        proposal_id = _proposal_id_from_metadata(approval.metadata)
        proposal = container.proposals.get(proposal_id) if proposal_id is not None else None
        return SemanticProposalRecord(proposal=proposal, approval=approval)

    proposal = container.proposals.get(ref)
    if proposal is not None:
        return SemanticProposalRecord(
            proposal=proposal,
            approval=_find_approval_for_proposal(
                approval_store,
                proposal.proposal_id,
            ),
        )

    approval = _find_approval_for_proposal(approval_store, ref)
    if approval is not None:
        proposal_id = _proposal_id_from_metadata(approval.metadata)
        proposal = container.proposals.get(proposal_id) if proposal_id is not None else None
        return SemanticProposalRecord(proposal=proposal, approval=approval)

    raise ValueError(f"semantic proposal or approval not found: {ref}")


def _find_approval_for_proposal(
    approval_store: JsonApprovalStore,
    proposal_id: str,
) -> ApprovalRequest | None:
    matches = [
        approval
        for approval in approval_store.list(limit=10_000)
        if approval.kind == "semantic_proposal"
        and _proposal_id_from_metadata(approval.metadata) == proposal_id
    ]
    return matches[0] if matches else None


def _execute_action(
    record: SemanticProposalRecord,
    *,
    action: str,
    container: SemanticMemoryContainer,
    approval_store: JsonApprovalStore,
    workspace_dir: str | None,
    actor: str,
    reason: str | None,
) -> tuple[SemanticProposal, ApprovalRequest | None, SemanticProposalApprovalOutcome]:
    if record.approval is not None and record.approval.status is ApprovalStatus.PENDING:
        return _execute_pending_approval_action(
            record,
            action=action,
            approval_store=approval_store,
            workspace_dir=workspace_dir,
            actor=actor,
            reason=reason,
            container=container,
        )

    return _execute_direct_proposal_action(
        record,
        action=action,
        actor=actor,
        reason=reason,
        container=container,
        approval_store=approval_store,
    )


def _execute_batch_action(
    records: Sequence[SemanticProposalRecord],
    *,
    action: str,
    container: SemanticMemoryContainer,
    approval_store: JsonApprovalStore,
    workspace_dir: str | None,
    actor: str,
    reason: str | None,
) -> list[SemanticProposalActionResult]:
    results: list[SemanticProposalActionResult] = []
    for record in records:
        results.append(
            _execute_action(
                record,
                action=action,
                container=container,
                approval_store=approval_store,
                workspace_dir=workspace_dir,
                actor=actor,
                reason=reason,
            )
        )
    return results


def _execute_pending_approval_action(
    record: SemanticProposalRecord,
    *,
    action: str,
    approval_store: JsonApprovalStore,
    workspace_dir: str | None,
    actor: str,
    reason: str | None,
    container: SemanticMemoryContainer,
) -> tuple[SemanticProposal, ApprovalRequest, SemanticProposalApprovalOutcome]:
    approval = record.approval
    if approval is None:
        raise ValueError("pending semantic approval is required")

    decision_status = (
        ApprovalStatus.REJECTED
        if action == "reject"
        else ApprovalStatus.APPROVED
    )
    response = (
        "apply"
        if action == "apply"
        else (reason or "reject")
        if action == "reject"
        else "approve"
    )
    resolved = approval_store.resolve(
        approval.approval_id,
        status=decision_status,
        response=response,
        source="cli",
        actor=actor,
    )
    if resolved is None:
        raise ValueError(f"approval not found: {approval.approval_id}")

    outcome = resolve_semantic_proposal_approval(
        resolved,
        workspace_dir=workspace_dir,
        reviewer=actor,
    )
    _attach_outcome_metadata(
        approval_store,
        resolved,
        outcome=outcome,
        response=response,
        source="cli",
        actor=actor,
    )
    proposal_id = _proposal_id_from_metadata(resolved.metadata)
    proposal = (
        container.proposals.get(proposal_id)
        if proposal_id is not None
        else None
    )
    if proposal is None:
        raise ValueError("semantic proposal record missing after approval resolution")
    return proposal, resolved, outcome


def _execute_direct_proposal_action(
    record: SemanticProposalRecord,
    *,
    action: str,
    actor: str,
    reason: str | None,
    container: SemanticMemoryContainer,
    approval_store: JsonApprovalStore,
) -> tuple[SemanticProposal, ApprovalRequest | None, SemanticProposalApprovalOutcome]:
    proposal = record.proposal
    if proposal is None:
        raise ValueError("semantic proposal not found")

    if action == "approve":
        proposal = container.review_semantic_proposal.execute(
            proposal.proposal_id,
            action="approve",
            reviewer=actor,
        ).proposal
        outcome = SemanticProposalApprovalOutcome(
            proposal_id=proposal.proposal_id,
            proposal_status=proposal.status.value,
            action="approve",
            applied=False,
        )
    elif action == "reject":
        proposal = container.review_semantic_proposal.execute(
            proposal.proposal_id,
            action="reject",
            reviewer=actor,
        ).proposal
        outcome = SemanticProposalApprovalOutcome(
            proposal_id=proposal.proposal_id,
            proposal_status=proposal.status.value,
            action="reject",
            applied=False,
        )
    else:
        if proposal.status is SemanticProposalStatus.PENDING and not proposal.auto_apply_eligible:
            proposal = container.review_semantic_proposal.execute(
                proposal.proposal_id,
                action="approve",
                reviewer=actor,
            ).proposal
        applied = container.apply_semantic_proposal.execute(
            proposal.proposal_id,
            reviewer=actor,
        )
        proposal = applied.proposal
        outcome = SemanticProposalApprovalOutcome(
            proposal_id=proposal.proposal_id,
            proposal_status=proposal.status.value,
            action="apply",
            applied=True,
            applied_target=applied.applied_target,
        )

    if record.approval is not None:
        response = (
            "apply"
            if action == "apply"
            else (reason or "reject")
            if action == "reject"
            else "approve"
        )
        _attach_outcome_metadata(
            approval_store,
            record.approval,
            outcome=outcome,
            response=response,
            source="cli",
            actor=actor,
        )
    return proposal, record.approval, outcome


def _attach_outcome_metadata(
    approval_store: JsonApprovalStore,
    approval: ApprovalRequest,
    *,
    outcome: SemanticProposalApprovalOutcome,
    response: str,
    source: str,
    actor: str,
) -> None:
    metadata = dict(approval.metadata or {})
    metadata["semanticProposalOutcome"] = {
        "proposalId": outcome.proposal_id,
        "proposalStatus": outcome.proposal_status,
        "action": outcome.action,
        "applied": outcome.applied,
        "appliedTarget": outcome.applied_target,
    }
    approval.metadata = metadata
    approval.response = response
    approval.source = source
    approval.actor = actor
    approval.updated_at = time.time()
    approval_store.replace(approval)


def _proposal_id_from_metadata(metadata: dict[str, object]) -> str | None:
    proposal_id = metadata.get("proposalId")
    if not isinstance(proposal_id, str) or not proposal_id.strip():
        return None
    return proposal_id.strip()


def _render_record_list(
    records: Sequence[SemanticProposalRecord],
    *,
    filters: SemanticProposalFilters,
) -> Table:
    table = Table(title=f"Semantic Proposals ({_describe_filters(filters)})")
    table.add_column("Proposal ID", style="bold")
    table.add_column("Approval ID")
    table.add_column("Type")
    table.add_column("Proposal")
    table.add_column("Approval")
    table.add_column("Risk")
    table.add_column("Conf")
    table.add_column("Summary")
    if not records:
        table.add_row("-", "-", "-", "-", "-", "-", "-", "No semantic proposals found")
        return table
    for record in records:
        proposal = record.proposal
        approval = record.approval
        table.add_row(
            proposal.proposal_id if proposal is not None else "-",
            approval.approval_id if approval is not None else "-",
            proposal.proposal_type.value if proposal is not None else "-",
            proposal.status.value if proposal is not None else "-",
            approval.status.value if approval is not None else "-",
            proposal.risk if proposal is not None else "-",
            (
                f"{proposal.confidence:.2f}"
                if proposal is not None
                else "-"
            ),
            proposal.summary
            if proposal is not None
            else approval.question
            if approval is not None
            else "-",
        )
    return table


def _render_batch_action_result(
    *,
    action: str,
    results: Sequence[SemanticProposalActionResult],
    filters: SemanticProposalFilters,
) -> Table:
    table = Table(title=f"Semantic Proposal Batch {action} ({_describe_filters(filters)})")
    table.add_column("Proposal ID", style="bold")
    table.add_column("Approval ID")
    table.add_column("Action")
    table.add_column("Proposal")
    table.add_column("Approval")
    table.add_column("Applied")
    table.add_column("Applied Target")
    table.add_column("Summary")
    if not results:
        table.add_row("-", "-", action, "-", "-", "False", "-", "No semantic proposals matched")
        return table
    for proposal, approval, outcome in results:
        table.add_row(
            proposal.proposal_id,
            approval.approval_id if approval is not None else "-",
            outcome.action,
            proposal.status.value,
            approval.status.value if approval is not None else "-",
            str(outcome.applied),
            outcome.applied_target or "-",
            proposal.summary,
        )
    return table


def _render_record_detail(record: SemanticProposalRecord) -> Table:
    proposal = record.proposal
    approval = record.approval
    table = Table(title="Semantic Proposal Detail")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    if proposal is None:
        table.add_row("proposal", "missing")
        if approval is not None:
            table.add_row("approval_id", approval.approval_id)
            table.add_row("approval_status", approval.status.value)
        return table

    table.add_row("proposal_id", proposal.proposal_id)
    table.add_row("proposal_type", proposal.proposal_type.value)
    table.add_row("proposal_status", proposal.status.value)
    table.add_row("target_id", proposal.target_id or "-")
    table.add_row("summary", proposal.summary)
    table.add_row("risk", proposal.risk)
    table.add_row("confidence", f"{proposal.confidence:.2f}")
    table.add_row("auto_apply_eligible", str(proposal.auto_apply_eligible))
    table.add_row("source_session_id", proposal.source_session_id or "-")
    table.add_row("source_run_id", proposal.source_run_id or "-")
    table.add_row("source_tool_name", proposal.source_tool_name or "-")
    table.add_row("evidence_refs", ", ".join(proposal.evidence_refs) or "-")
    table.add_row(
        "payload",
        json.dumps(
            proposal.payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
    )
    if approval is not None:
        table.add_row("approval_id", approval.approval_id)
        table.add_row("approval_status", approval.status.value)
        table.add_row("approval_response", approval.response or "-")
    return table


def _render_action_result(
    *,
    proposal: SemanticProposal,
    approval: ApprovalRequest | None,
    outcome: SemanticProposalApprovalOutcome,
) -> Table:
    table = Table(title="Semantic Proposal Action")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("proposal_id", proposal.proposal_id)
    table.add_row("action", outcome.action)
    table.add_row("proposal_status", outcome.proposal_status)
    table.add_row("approval_id", approval.approval_id if approval is not None else "-")
    table.add_row("approval_status", approval.status.value if approval is not None else "-")
    table.add_row("applied", str(outcome.applied))
    table.add_row("applied_target", outcome.applied_target or "-")
    table.add_row("summary", proposal.summary)
    return table


def _describe_filters(filters: SemanticProposalFilters) -> str:
    parts: list[str] = []
    parts.append(
        "approval="
        + (
            filters.approval_status.value
            if filters.approval_status is not None
            else "all"
        )
    )
    if filters.proposal_status is not None:
        parts.append(f"proposal={filters.proposal_status.value}")
    if filters.proposal_type is not None:
        parts.append(f"type={filters.proposal_type.value}")
    if filters.risk is not None:
        parts.append(f"risk={filters.risk}")
    if filters.session_id is not None:
        parts.append(f"session={filters.session_id}")
    return ", ".join(parts)
