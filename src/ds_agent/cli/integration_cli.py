"""Integration health CLI helpers."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from rich.console import Console
from rich.table import Table

from ds_agent.infrastructure.work_object_container import build_work_object_container


def run_integration_command(
    argv: Sequence[str],
    *,
    workspace_dir: str = ".",
) -> None:
    parser = argparse.ArgumentParser(prog="ds-agent integration")
    sub = parser.add_subparsers(dest="subcmd")
    sub.add_parser("health", help="Check connector health")

    dlq_cmd = sub.add_parser("dlq", help="List failed/DLQ events")
    dlq_cmd.add_argument("--system", default=None, help="Filter by system")
    dlq_cmd.add_argument(
        "--limit", type=int, default=20, help="Max events",
    )

    replay_cmd = sub.add_parser("replay", help="Replay a failed event")
    replay_cmd.add_argument("event_id", help="Event ID to replay")

    args = parser.parse_args(argv)

    if args.subcmd == "health":
        _health(workspace_dir=workspace_dir)
    elif args.subcmd == "dlq":
        _dlq(
            workspace_dir=workspace_dir,
            system=args.system,
            limit=args.limit,
        )
    elif args.subcmd == "replay":
        _replay(workspace_dir=workspace_dir, event_id=args.event_id)
    else:
        parser.print_help()


def _health(*, workspace_dir: str) -> None:
    console = Console()
    container = build_work_object_container(workspace_dir)
    hub = container.hub
    results = hub.health_check_all()

    table = Table(title="Integration Connector Health")
    table.add_column("System", style="bold")
    table.add_column("Status")
    table.add_column("Message")
    table.add_column("Latency (ms)", justify="right")

    for r in results:
        status_style = "green" if r.healthy else "red"
        status_text = "Healthy" if r.healthy else "Unhealthy"
        latency = f"{r.latency_ms:.1f}" if r.latency_ms is not None else "-"
        styled = f"[{status_style}]{status_text}[/{status_style}]"
        table.add_row(r.system, styled, r.message, latency)

    console.print(table)


def _dlq(*, workspace_dir: str, system: str | None, limit: int) -> None:
    from ds_agent.domain.entities.integration_event import (
        IntegrationEventStatus,
    )

    console = Console()
    container = build_work_object_container(workspace_dir)
    store = container.store

    failed = store.list_events_by_status(
        IntegrationEventStatus.FAILED, system=system, limit=limit,
    )
    dlq = store.list_events_by_status(
        IntegrationEventStatus.DLQ, system=system, limit=limit,
    )
    events = dlq + failed
    events.sort(key=lambda e: e.started_at, reverse=True)
    events = events[:limit]

    if not events:
        console.print("[green]No failed or DLQ events found.[/]")
        return

    table = Table(title="Failed / DLQ Integration Events")
    table.add_column("Event ID", style="bold")
    table.add_column("Status")
    table.add_column("System")
    table.add_column("Action")
    table.add_column("Attempt", justify="right")
    table.add_column("Error")
    table.add_column("Started At")

    for e in events:
        s_style = "yellow" if e.status == IntegrationEventStatus.FAILED else "red"
        table.add_row(
            e.event_id,
            f"[{s_style}]{e.status.value}[/{s_style}]",
            e.system,
            e.action,
            str(e.attempt),
            (e.error_message or "-")[:60],
            str(e.started_at)[:19],
        )

    console.print(table)


def _replay(*, workspace_dir: str, event_id: str) -> None:
    console = Console()
    container = build_work_object_container(workspace_dir)
    hub = container.hub

    try:
        result = hub.replay_event(event_id)
    except ValueError as exc:
        console.print(f"[red]Error:[/] {exc}")
        return

    if result["success"]:
        console.print(
            f"[green]Replay succeeded.[/] "
            f"New event: {result['replay_event_id']} "
            f"(attempt {result['attempt']})",
        )
    else:
        console.print(
            f"[yellow]Replay failed.[/] "
            f"New event: {result['replay_event_id']} "
            f"(attempt {result['attempt']}) — "
            f"{result.get('error_message', 'unknown error')}",
        )
