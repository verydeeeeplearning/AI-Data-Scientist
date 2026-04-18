"""Stakeholder delivery CLI helpers."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import TYPE_CHECKING

from rich.console import Console

from ds_agent.application.dtos.task_contract import (
    BuildDeliveryPackDTO,
    DispatchDeliveryDTO,
    ListDeliveryLogDTO,
    RenderDeliveryArtifactDTO,
)
from ds_agent.domain.entities.delivery_pack import AudienceKind, DeliveryChannel
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.infrastructure.task_contract_container import (
    TaskContractContainer,
    build_task_contract_container,
)
from ds_agent.presentation.delivery_presenters import (
    load_delivery_analysis,
    parse_delivery_context,
    render_delivery_build,
    render_delivery_dispatch,
    render_delivery_log,
    render_delivery_render,
)
from ds_agent.runtime.provider_factory import create_auth_profile_store, create_provider_router

if TYPE_CHECKING:
    from ds_agent.config.schema import DSAgentConfig
    from ds_agent.domain.interfaces.llm_provider import LLMProvider


def run_delivery_command(
    argv: Sequence[str],
    *,
    console: Console,
    workspace_dir: str | None,
    config: DSAgentConfig | None = None,
) -> int:
    """Run `ds-agent delivery ...`."""

    parser = _build_parser()
    args = parser.parse_args(list(argv))
    if args.command == "render" and args.model and not args.provider_backed:
        parser.error("--model requires --provider-backed")
    container, renderer_model = _resolve_container(
        command=args.command,
        workspace_dir=workspace_dir,
        config=config,
        provider_backed=getattr(args, "provider_backed", False),
        model=getattr(args, "model", None),
    )

    if args.command == "build":
        result = container.build_delivery_pack.execute(
            BuildDeliveryPackDTO.model_validate(
                {
                    "task_id": args.task_id,
                    "audiences": list(args.audience or []),
                    "follow_up_actions": list(args.follow_up or []),
                    "source_analysis_id": args.source_analysis_id,
                    "confidence": args.confidence,
                    "signed_by": args.signed_by,
                    "signature": args.signature,
                    "global_context": parse_delivery_context(args.context or []),
                    "tenant": args.tenant,
                }
            )
        )
        console.print(render_delivery_build(result))
        return 0

    if args.command == "render":
        result = container.render_delivery_artifact.execute(
            RenderDeliveryArtifactDTO.model_validate(
                {
                    "task_id": args.task_id,
                    "artifact_id": args.artifact_id,
                    "analysis": load_delivery_analysis(
                        analysis_json=args.analysis_json,
                        analysis_file=args.analysis_file,
                    ),
                    "output_dir": args.output_dir,
                    "audience_profile": args.audience_profile,
                }
            )
        )
        if renderer_model is not None:
            result["renderer_mode"] = "provider-backed"
            result["renderer_model"] = renderer_model
        console.print(render_delivery_render(result))
        return 0

    if args.command == "dispatch":
        result = container.dispatch_delivery.execute(
            DispatchDeliveryDTO.model_validate(
                {
                    "task_id": args.task_id,
                    "artifact_ids": list(args.artifact_id or []),
                    "channels": list(args.channel or []),
                    "dry_run": args.dry_run,
                    "approve_manual_review": args.approve_manual_review,
                }
            )
        )
        console.print(render_delivery_dispatch(result))
        return 0

    result = container.list_delivery_log.execute(
        ListDeliveryLogDTO.model_validate(
            {
                "task_id": args.task_id,
                "pack_id": args.pack_id,
                "artifact_ids": list(args.artifact_id or []),
                "channels": list(args.channel or []),
                "limit": args.limit,
            }
        )
    )
    console.print(render_delivery_log(result))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ds-agent delivery", add_help=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", add_help=False)
    build.add_argument("task_id")
    build.add_argument(
        "--audience",
        action="append",
        choices=[item.value for item in AudienceKind],
        default=[],
    )
    build.add_argument("--follow-up", action="append", default=[])
    build.add_argument("--source-analysis-id")
    build.add_argument("--confidence", type=float)
    build.add_argument("--signed-by")
    build.add_argument("--signature")
    build.add_argument("--tenant", default="default")
    build.add_argument("--context", action="append", default=[])

    render = subparsers.add_parser("render", add_help=False)
    render.add_argument("task_id")
    render.add_argument("artifact_id")
    render.add_argument("--analysis-json")
    render.add_argument("--analysis-file")
    render.add_argument("--output-dir", required=True)
    render.add_argument(
        "--audience-profile",
        choices=[item.value for item in AudiencePersona],
    )
    render.add_argument("--provider-backed", action="store_true")
    render.add_argument("--model")

    dispatch = subparsers.add_parser("dispatch", add_help=False)
    dispatch.add_argument("task_id")
    dispatch.add_argument("--artifact-id", action="append", default=[])
    dispatch.add_argument(
        "--channel",
        action="append",
        choices=[item.value for item in DeliveryChannel],
        default=[],
    )
    dispatch.add_argument("--dry-run", action="store_true")
    dispatch.add_argument("--approve-manual-review", action="store_true")

    log = subparsers.add_parser("log", add_help=False)
    log.add_argument("task_id")
    log.add_argument("--pack-id")
    log.add_argument("--artifact-id", action="append", default=[])
    log.add_argument(
        "--channel",
        action="append",
        choices=[item.value for item in DeliveryChannel],
        default=[],
    )
    log.add_argument("--limit", type=int, default=50)

    return parser


def _resolve_container(
    *,
    command: str,
    workspace_dir: str | None,
    config: DSAgentConfig | None,
    provider_backed: bool,
    model: str | None,
) -> tuple[TaskContractContainer, str | None]:
    if command != "render" or not provider_backed:
        return build_task_contract_container(workspace_dir), None
    provider, resolved_model = _resolve_provider_backed_renderer(config=config, model=model)
    return (
        build_task_contract_container(workspace_dir, llm_provider=provider),
        resolved_model,
    )


def _resolve_provider_backed_renderer(
    *,
    config: DSAgentConfig | None,
    model: str | None,
) -> tuple[LLMProvider, str]:
    resolved_config = config
    if resolved_config is None:
        from ds_agent.config.loader import get_default_config_path, load_config

        resolved_config = load_config(get_default_config_path())
    resolved_model = model or resolved_config.provider.default_model
    token_store = create_auth_profile_store(resolved_config)
    provider = create_provider_router(
        resolved_model,
        resolved_config,
        token_store=token_store,
    )
    return provider, resolved_model
