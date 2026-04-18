"""CLI subcommands for self-improvement governance."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore


def run_learning_command(
    argv: Sequence[str],
    *,
    workspace_dir: str = ".",
    console: Console | None = None,
) -> int:
    """Entry point for ``ds-agent learning`` subcommands."""
    console = console or Console()
    parser = argparse.ArgumentParser(prog="ds-agent learning")
    sub = parser.add_subparsers(dest="subcmd")

    inbox_cmd = sub.add_parser("inbox", help="Show learning inbox")
    inbox_cmd.add_argument("--status", default="proposed")
    inbox_cmd.add_argument("--type", default=None)
    inbox_cmd.add_argument("--limit", type=int, default=20)

    review_cmd = sub.add_parser("review", help="Review a learning item")
    review_cmd.add_argument("item_id")
    review_cmd.add_argument("--decision", required=True, choices=["approve", "modify", "reject"])
    review_cmd.add_argument("--comment", default="")

    sub.add_parser("promotions", help="List promotion records")
    sub.add_parser("deprecations", help="List deprecation records")

    rollback_cmd = sub.add_parser("rollback", help="Rollback a promoted item")
    rollback_cmd.add_argument("item_id")
    rollback_cmd.add_argument("--reason", default="manual rollback")

    args = parser.parse_args(argv)

    if args.subcmd == "inbox":
        return _inbox(
            console, workspace_dir,
            status=args.status, item_type=args.type, limit=args.limit,
        )
    if args.subcmd == "review":
        return _review(
            console, workspace_dir,
            item_id=args.item_id, decision=args.decision, comment=args.comment,
        )
    if args.subcmd == "promotions":
        return _promotions(console, workspace_dir)
    if args.subcmd == "deprecations":
        return _deprecations(console, workspace_dir)
    if args.subcmd == "rollback":
        return _rollback(console, workspace_dir, item_id=args.item_id, reason=args.reason)

    parser.print_help()
    return 0


def _get_store(workspace_dir: str) -> SqliteLearningStore:
    from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore

    return SqliteLearningStore.for_workspace(workspace_dir)


def _inbox(
    console: Console,
    workspace_dir: str,
    *,
    status: str,
    item_type: str | None,
    limit: int,
) -> int:
    from datetime import UTC, datetime

    from ds_agent.application.learning.learning_inbox import LearningInboxUseCase
    from ds_agent.domain.learning.learning_item import (
        LearningItemStatus,
        LearningItemType,
    )

    class _Clock:
        def now(self) -> datetime:
            return datetime.now(UTC)

    store = _get_store(workspace_dir)
    uc = LearningInboxUseCase(store, _Clock())

    status_filter = [LearningItemStatus(status)] if status != "all" else None
    type_filter = LearningItemType(item_type) if item_type else None

    scored = uc.execute(
        status_filter=status_filter,
        item_type_filter=type_filter,
        limit=limit,
    )

    if not scored:
        console.print("[dim]No items in the learning inbox.[/dim]")
        return 0

    table = Table(title="Learning Inbox")
    table.add_column("ID", style="cyan")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Title")
    table.add_column("Priority", justify="right")
    table.add_column("Evidence", justify="right")
    table.add_column("Scope")

    for s in scored:
        table.add_row(
            s.item.item_id,
            s.item.item_type.value,
            s.item.status.value,
            s.item.title[:40],
            f"{s.priority_score:.2f}",
            str(len(s.item.evidence)),
            s.item.scope,
        )
    console.print(table)
    return 0


def _review(
    console: Console,
    workspace_dir: str,
    *,
    item_id: str,
    decision: str,
    comment: str,
) -> int:
    from datetime import UTC, datetime

    from ds_agent.application.learning.review_learning_item import (
        ReviewLearningItemUseCase,
    )
    from ds_agent.domain.learning.review_event import ReviewChecklist, ReviewDecision

    class _Clock:
        def now(self) -> datetime:
            return datetime.now(UTC)

    store = _get_store(workspace_dir)
    dec = ReviewDecision(decision)
    checklist = ReviewChecklist(
        evidence_sufficient=True,
        no_unresolved_conflicts=True,
        scope_appropriate=True,
        content_accurate=True,
    ) if dec == ReviewDecision.APPROVE else None

    uc = ReviewLearningItemUseCase(store, _Clock())
    try:
        updated, _event = uc.execute(
            item_id=item_id,
            decision=dec,
            reviewer="cli-operator",
            checklist=checklist,
            comment=comment,
        )
    except ValueError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        return 1

    console.print(
        f"[green]{decision.capitalize()}d[/green] {item_id} -> {updated.status.value}"
    )
    return 0


def _promotions(console: Console, workspace_dir: str) -> int:
    store = _get_store(workspace_dir)
    records = store.list_promotion_records(limit=20)
    if not records:
        console.print("[dim]No promotion records.[/dim]")
        return 0

    table = Table(title="Promotion Records")
    table.add_column("Record ID", style="cyan")
    table.add_column("Item ID")
    table.add_column("Type")
    table.add_column("Score", justify="right")
    table.add_column("Promoted At")

    for r in records:
        table.add_row(
            r.record_id,
            r.item_id,
            r.item_type.value,
            f"{r.eval_score:.3f}",
            r.promoted_at.isoformat(),
        )
    console.print(table)
    return 0


def _deprecations(console: Console, workspace_dir: str) -> int:
    store = _get_store(workspace_dir)
    records = store.list_deprecation_records(limit=20)
    if not records:
        console.print("[dim]No deprecation records.[/dim]")
        return 0

    table = Table(title="Deprecation Records")
    table.add_column("Record ID", style="cyan")
    table.add_column("Item ID")
    table.add_column("Reason")
    table.add_column("Mode")
    table.add_column("Failures", justify="right")
    table.add_column("Deprecated At")

    for r in records:
        table.add_row(
            r.record_id,
            r.item_id,
            r.reason.value,
            r.mode.value,
            str(r.failure_count),
            r.deprecated_at.isoformat(),
        )
    console.print(table)
    return 0


def _rollback(
    console: Console,
    workspace_dir: str,
    *,
    item_id: str,
    reason: str,
) -> int:
    from datetime import UTC, datetime

    from ds_agent.application.learning.rollback_promotion import (
        RollbackPromotionUseCase,
    )

    class _Clock:
        def now(self) -> datetime:
            return datetime.now(UTC)

    store = _get_store(workspace_dir)
    uc = RollbackPromotionUseCase(store, _Clock())
    try:
        updated, dep_record = uc.execute(item_id=item_id, reason=reason)
    except ValueError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        return 1

    console.print(
        f"[green]Rolled back[/green] {item_id} -> {updated.status.value} "
        f"(record: {dep_record.record_id})"
    )
    return 0
