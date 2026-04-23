"""Task contract CLI helpers."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from rich.console import Console

from ds_agent.application.dtos.task_contract import TaskContractViewDTO
from ds_agent.domain.entities.task_contract import TaskContractStatus
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.services.task_contract_state_machine import TaskContractValidator
from ds_agent.infrastructure.task_contract_container import build_task_contract_container
from ds_agent.presentation.task_contract_presenters import (
    render_task_contract_json,
    render_task_contract_list,
    render_task_contract_markdown,
    render_task_contract_summary,
)

_INCLUDE_ALL = [
    "goal_brief",
    "metric_specs",
    "dataset_manifest",
    "assumption_log",
    "review_verdicts",
    "delivery_pack",
]


def run_contract_command(
    argv: Sequence[str],
    *,
    console: Console,
    workspace_dir: str | None,
    default_session_id: str | None = None,
) -> int:
    """Run `ds-agent contract ...` or `/contract ...`."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) or ["active"])
    container = build_task_contract_container(workspace_dir)

    if args.command == "active":
        session_id = args.session_id or default_session_id
        if not session_id:
            console.print("Session id is required. Pass `--session-id` after the first run.")
            return 1
        view = _get_active_view(
            container.store.get_active_bundle(session_id),
            mission_required_artifact_resolver=container.mission_required_artifact_resolver,
            mission_required_delivery_channel_resolver=(
                container.mission_required_delivery_channel_resolver
            ),
        )
        if view is None:
            console.print("No active task contract for this session.")
            return 0
        console.print(render_task_contract_summary(view))
        return 0

    if args.command == "list":
        statuses = [TaskContractStatus(item) for item in args.status] if args.status else None
        items = container.list_contracts.execute(
            args.session_id or default_session_id,
            status_filter=statuses,
            limit=args.limit,
        )
        console.print(render_task_contract_list(items))
        return 0

    view = container.get.execute(args.task_id, include=_INCLUDE_ALL)
    if args.command == "show":
        console.print(render_task_contract_summary(view))
        return 0

    exported = (
        render_task_contract_json(view)
        if args.format == "json"
        else render_task_contract_markdown(view)
    )
    sys.stdout.write(exported + "\n")
    return 0


def show_active_task_contract(
    *,
    console: Console,
    workspace_dir: str | None,
    session_id: str | None,
) -> bool:
    """Print the active contract for the current interactive session."""

    return (
        run_contract_command(
            [],
            console=console,
            workspace_dir=workspace_dir,
            default_session_id=session_id,
        )
        == 0
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ds-agent contract", add_help=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    active = subparsers.add_parser("active", add_help=False)
    active.add_argument("--session-id")

    list_cmd = subparsers.add_parser("list", add_help=False)
    list_cmd.add_argument("--session-id")
    list_cmd.add_argument(
        "--status",
        nargs="*",
        choices=[item.value for item in TaskContractStatus],
    )
    list_cmd.add_argument("--limit", type=int, default=20)

    show = subparsers.add_parser("show", add_help=False)
    show.add_argument("task_id")

    export = subparsers.add_parser("export", add_help=False)
    export.add_argument("task_id")
    export.add_argument("--format", choices=["json", "md"], default="json")

    return parser


def _get_active_view(
    bundle: TaskContractBundle | None,
    *,
    mission_required_artifact_resolver: object | None = None,
    mission_required_delivery_channel_resolver: object | None = None,
) -> TaskContractViewDTO | None:
    if bundle is None:
        return None
    resolve_for_bundle = getattr(mission_required_artifact_resolver, "resolve_for_bundle", None)
    mission_artifact_resolution = (
        resolve_for_bundle(bundle) if callable(resolve_for_bundle) else None
    )
    resolve_delivery_for_bundle = getattr(
        mission_required_delivery_channel_resolver,
        "resolve_for_bundle",
        None,
    )
    mission_delivery_channel_resolution = (
        resolve_delivery_for_bundle(bundle) if callable(resolve_delivery_for_bundle) else None
    )
    return TaskContractViewDTO.from_bundle(
        bundle,
        include=set(_INCLUDE_ALL),
        dod_summary=TaskContractValidator.build_dod_summary(
            bundle,
            mission_artifact_resolution=mission_artifact_resolution,
            mission_delivery_channel_resolution=mission_delivery_channel_resolution,
        ),
    )
