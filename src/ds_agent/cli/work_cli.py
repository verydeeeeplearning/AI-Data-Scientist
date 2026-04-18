"""Work object CLI helpers."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

from rich.console import Console

from ds_agent.application.dtos.work_object import (
    AdvanceWorkObjectPhaseDTO,
    CloseWorkObjectDTO,
    CreateWorkObjectDTO,
    ListWorkObjectsDTO,
)
from ds_agent.domain.entities.external_reference import build_integration_idempotency_key
from ds_agent.domain.entities.work_object import RequestSource, WorkObjectPhase
from ds_agent.infrastructure.work_object_container import build_work_object_container
from ds_agent.presentation.work_object_presenters import (
    parse_work_metadata,
    render_work_object_list,
    render_work_object_timeline,
    render_work_object_view,
)


def run_work_command(
    argv: Sequence[str],
    *,
    console: Console,
    workspace_dir: str | None,
) -> int:
    """Run `ds-agent work ...`."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) or ["list"])
    container = build_work_object_container(workspace_dir)

    if args.command == "intake":
        created_view = container.create.execute(
            CreateWorkObjectDTO.model_validate(
                {
                    "task_contract_id": args.task_contract_id,
                    "title": args.title,
                    "request_source": args.source,
                    "requestor_id": args.requestor_id,
                    "requestor_display": args.requestor_display,
                    "original_text": args.text,
                    "channel": args.channel,
                    "request_metadata": parse_work_metadata(args.metadata or []),
                    "external_reference": _build_external_reference_payload(args),
                    "delivery_pack_id": args.delivery_pack_id,
                    "owner_agent": args.owner_agent,
                    "tags": list(args.tag or []),
                    "parent_work_object_id": args.parent_work_object_id,
                }
            )
        )
        console.print(render_work_object_view(created_view))
        return 0

    if args.command == "list":
        items = container.list_work_objects.execute(
            ListWorkObjectsDTO.model_validate(
                {
                    "session_id": args.session_id,
                    "task_contract_id": args.task_contract_id,
                    "phase_filter": args.phase or [],
                    "limit": args.limit,
                }
            )
        )
        console.print(render_work_object_list(items))
        return 0

    if args.command == "show":
        view = container.get.execute(args.work_object_id, timeline_limit=args.timeline_limit)
        console.print(render_work_object_view(view))
        return 0

    if args.command == "timeline":
        events = container.timeline.execute(args.work_object_id, limit=args.limit)
        console.print(render_work_object_timeline(events))
        return 0

    if args.command == "advance":
        advance_result = container.advance_phase.execute(
            AdvanceWorkObjectPhaseDTO.model_validate(
                {
                    "work_object_id": args.work_object_id,
                    "to_phase": args.to_phase,
                    "run_id": args.run_id,
                }
            )
        )
        run_ids = [
            str(item)
            for item in cast(list[object], advance_result.get("run_ids", []))
        ]
        console.print(
            "\n".join(
                [
                    f"Work object: {advance_result['work_object_id']}",
                    f"Phase: {advance_result['phase']}",
                    f"Runs: {', '.join(run_ids) or '-'}",
                ]
            )
        )
        return 0

    close_result = container.close.execute(
        CloseWorkObjectDTO.model_validate(
            {"work_object_id": args.work_object_id, "reason": args.reason}
        )
    )
    console.print(
        "\n".join(
            [
                f"Work object: {close_result['work_object_id']}",
                f"Phase: {close_result['phase']}",
                f"Reason: {close_result['close_reason']}",
            ]
        )
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ds-agent work", add_help=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    intake_cmd = subparsers.add_parser("intake", add_help=False)
    intake_cmd.add_argument("task_contract_id")
    intake_cmd.add_argument("--title", required=True)
    intake_cmd.add_argument(
        "--source",
        required=True,
        choices=[source.value for source in RequestSource],
    )
    intake_cmd.add_argument("--requestor-id", required=True)
    intake_cmd.add_argument("--requestor-display", required=True)
    intake_cmd.add_argument("--text", required=True)
    intake_cmd.add_argument("--channel")
    intake_cmd.add_argument("--metadata", action="append", default=[])
    intake_cmd.add_argument("--external-system")
    intake_cmd.add_argument("--external-resource-type")
    intake_cmd.add_argument("--external-resource-id")
    intake_cmd.add_argument("--external-url")
    intake_cmd.add_argument("--delivery-pack-id")
    intake_cmd.add_argument("--owner-agent", default="ds-agent")
    intake_cmd.add_argument("--tag", action="append", default=[])
    intake_cmd.add_argument("--parent-work-object-id")

    list_cmd = subparsers.add_parser("list", add_help=False)
    list_cmd.add_argument("--session-id")
    list_cmd.add_argument("--task-contract-id")
    list_cmd.add_argument(
        "--phase",
        nargs="*",
        choices=[phase.value for phase in WorkObjectPhase],
    )
    list_cmd.add_argument("--limit", type=int, default=20)

    show_cmd = subparsers.add_parser("show", add_help=False)
    show_cmd.add_argument("work_object_id")
    show_cmd.add_argument("--timeline-limit", type=int, default=20)

    timeline_cmd = subparsers.add_parser("timeline", add_help=False)
    timeline_cmd.add_argument("work_object_id")
    timeline_cmd.add_argument("--limit", type=int, default=20)

    advance_cmd = subparsers.add_parser("advance", add_help=False)
    advance_cmd.add_argument("work_object_id")
    advance_cmd.add_argument(
        "--to-phase",
        required=True,
        choices=[phase.value for phase in WorkObjectPhase],
    )
    advance_cmd.add_argument("--run-id")

    close_cmd = subparsers.add_parser("close", add_help=False)
    close_cmd.add_argument("work_object_id")
    close_cmd.add_argument("--reason", required=True)

    return parser


def _build_external_reference_payload(args: argparse.Namespace) -> dict[str, object] | None:
    system = getattr(args, "external_system", None)
    resource_type = getattr(args, "external_resource_type", None)
    resource_id = getattr(args, "external_resource_id", None)
    if not system and not resource_type and not resource_id:
        return None
    if not system or not resource_type or not resource_id:
        raise ValueError(
            "external reference requires --external-system, --external-resource-type, "
            "and --external-resource-id together"
        )
    return {
        "system": system,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "url": getattr(args, "external_url", None),
        "metadata": {},
        "created_at": datetime.now(UTC).isoformat(),
        "idempotency_key": build_integration_idempotency_key(
            work_object_id=f"task-{args.task_contract_id}",
            system=system,
            action="intake_request",
            discriminator=resource_id,
        ),
    }
