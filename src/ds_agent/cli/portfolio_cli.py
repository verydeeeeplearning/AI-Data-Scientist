"""CLI subcommands for async portfolio management."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from ds_agent.infrastructure.persistence.portfolio_store import SqlitePortfolioStore


def run_portfolio_command(
    argv: Sequence[str],
    *,
    workspace_dir: str = ".",
    console: Console | None = None,
) -> int:
    """Entry point for ``ds-agent portfolio`` subcommands."""
    console = console or Console()
    parser = argparse.ArgumentParser(prog="ds-agent portfolio")
    sub = parser.add_subparsers(dest="subcmd")

    list_cmd = sub.add_parser("list", help="List portfolio entries")
    list_cmd.add_argument("--quadrant", default=None, help="Filter by quadrant")
    list_cmd.add_argument("--limit", type=int, default=20)

    show_cmd = sub.add_parser("show", help="Show portfolio entry detail")
    show_cmd.add_argument("entry_id", help="Portfolio entry ID")

    sub.add_parser("ticks", help="Evaluate wait conditions and show resumable tasks")

    args = parser.parse_args(argv)

    if args.subcmd == "list":
        return _list(console, workspace_dir, quadrant=args.quadrant, limit=args.limit)
    if args.subcmd == "show":
        return _show(console, workspace_dir, entry_id=args.entry_id)
    if args.subcmd == "ticks":
        return _ticks(console, workspace_dir)

    parser.print_help()
    return 0


def _get_store(workspace_dir: str) -> SqlitePortfolioStore:
    from ds_agent.infrastructure.persistence.portfolio_store import SqlitePortfolioStore

    return SqlitePortfolioStore.for_workspace(workspace_dir)


def _list(
    console: Console,
    workspace_dir: str,
    *,
    quadrant: str | None,
    limit: int,
) -> int:
    store = _get_store(workspace_dir)
    entries = store.list_entries(quadrant=quadrant, limit=limit)
    if not entries:
        console.print("[dim]No portfolio entries found.[/dim]")
        return 0

    table = Table(title="Portfolio Entries")
    table.add_column("Entry ID", style="cyan")
    table.add_column("Task Contract")
    table.add_column("Quadrant", style="bold")
    table.add_column("Priority")
    table.add_column("SLA Deadline")
    table.add_column("Tags")

    for e in entries:
        table.add_row(
            e.entry_id,
            e.task_contract_id,
            e.quadrant,
            e.business_priority.value,
            e.sla_deadline.isoformat() if e.sla_deadline else "-",
            ", ".join(e.tags) or "-",
        )
    console.print(table)
    return 0


def _show(console: Console, workspace_dir: str, *, entry_id: str) -> int:
    store = _get_store(workspace_dir)
    entry = store.get_entry(entry_id)
    if entry is None:
        console.print(f"[red]Portfolio entry {entry_id} not found.[/red]")
        return 1

    console.print(f"[bold cyan]{entry.entry_id}[/bold cyan]")
    console.print(f"  Task Contract: {entry.task_contract_id}")
    console.print(f"  Quadrant:      {entry.quadrant}")
    console.print(f"  Priority:      {entry.business_priority.value}")
    console.print(f"  SLA Deadline:  {entry.sla_deadline or '-'}")
    console.print(f"  Run ID:        {entry.parent_run_id or '-'}")
    console.print(f"  Wait Cond:     {entry.wait_condition_id or '-'}")
    console.print(f"  Monitor Ref:   {entry.monitoring_metric_ref or '-'}")
    console.print(f"  Tags:          {', '.join(entry.tags) or '-'}")
    console.print(f"  Created:       {entry.created_at.isoformat()}")
    console.print(f"  Updated:       {entry.updated_at.isoformat()}")

    transitions = store.list_transitions(entry_id, limit=10)
    if transitions:
        console.print("\n[bold]Recent Transitions[/bold]")
        for t in transitions:
            console.print(
                f"  {t.at.isoformat()}  {t.from_quadrant or '(new)'} → {t.to_quadrant}  "
                f"[dim]{t.reason} ({t.actor})[/dim]",
            )
    return 0


def _ticks(console: Console, workspace_dir: str) -> int:
    from dataclasses import dataclass
    from datetime import UTC, datetime

    from ds_agent.application.portfolio.portfolio_evaluator import PortfolioEvaluator
    from ds_agent.application.portfolio.priority_calculator import PriorityCalculator
    from ds_agent.application.portfolio.slot_manager import SlotManager
    from ds_agent.application.portfolio.wait_condition_evaluator import WaitConditionEvaluator

    @dataclass
    class _Clock:
        def now(self) -> datetime:
            return datetime.now(UTC)

    store = _get_store(workspace_dir)
    clock = _Clock()
    evaluator = PortfolioEvaluator(
        store=store,
        slot_manager=SlotManager(store),
        condition_evaluator=WaitConditionEvaluator(clock),
        priority_calculator=PriorityCalculator(clock),
    )
    snapshot = evaluator.evaluate()

    console.print("[bold]Portfolio Snapshot[/bold]")
    console.print(
        f"  Active: {len(snapshot.active_entries)}  "
        f"Waiting: {len(snapshot.waiting_entries)}  "
        f"Monitoring: {len(snapshot.monitoring_entries)}  "
        f"Candidates: {len(snapshot.candidate_entries)}",
    )
    console.print(
        f"  Slots: {snapshot.active_slot_count}/{snapshot.max_slots} "
        f"({snapshot.available_slots} available)",
    )
    if snapshot.sla_at_risk_count > 0:
        console.print(f"  [red]SLA at risk: {snapshot.sla_at_risk_count}[/red]")

    if snapshot.resumable_conditions:
        console.print("\n[bold green]Resumable Conditions[/bold green]")
        for r in snapshot.resumable_conditions:
            console.print(f"  {r.condition_id}  {r.kind}  {r.reason}")
    else:
        console.print("\n[dim]No resumable conditions.[/dim]")

    if snapshot.priority_ranking:
        console.print("\n[bold]Priority Ranking[/bold]")
        table = Table()
        table.add_column("Entry ID", style="cyan")
        table.add_column("Score", justify="right")
        table.add_column("SLA Urgency", justify="right")
        table.add_column("Biz Weight", justify="right")
        for s in snapshot.priority_ranking[:10]:
            table.add_row(
                s.entry_id,
                f"{s.raw_score:.1f}",
                f"{s.sla_urgency:.1f}",
                f"{s.business_weight:.1f}",
            )
        console.print(table)

    return 0
