"""Autonomy certification CLI helpers."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from rich.console import Console

from ds_agent.application.services.certification_usecases import (
    CertificationStatusResult,
    GetCertificationStatusUseCase,
    SubmitCertificationInput,
    SubmitCertificationResult,
    SubmitCertificationUseCase,
)
from ds_agent.infrastructure.persistence.certification_store import SqliteCertificationStore
from ds_agent.presentation.certification_presenters import (
    render_certification_status,
    render_certification_submission,
)
from ds_agent.skills.mission_pack_loader import MissionPackLoader


def run_certification_command(
    argv: Sequence[str],
    *,
    console: Console,
    workspace_dir: str | None,
) -> int:
    """Run `ds-agent certification ...`."""

    parser = _build_parser()
    args = parser.parse_args(list(argv))
    mission_loader = MissionPackLoader()
    store = SqliteCertificationStore.for_workspace(workspace_dir)

    if args.command == "status":
        status_result = GetCertificationStatusUseCase(mission_loader, store).execute(
            args.mission_name
        )
        _render_status(console, status_result)
        return 0

    submit_result = SubmitCertificationUseCase(mission_loader, store).execute(
        SubmitCertificationInput(
            mission_name=args.mission_name,
            target_level=args.to,
            approved_by=tuple(args.approved_by or ()),
            evidence_ref=args.evidence_ref,
        )
    )
    _render_submit(console, submit_result)
    return 0


def show_certification_status(
    *,
    console: Console,
    workspace_dir: str | None,
    mission_name: str | None,
) -> bool:
    """Print certification status for one mission."""

    if not mission_name:
        console.print("Usage: /certification <mission-name>")
        return True
    return (
        run_certification_command(
            ["status", mission_name],
            console=console,
            workspace_dir=workspace_dir,
        )
        == 0
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ds-agent certification", add_help=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", add_help=False)
    status.add_argument("mission_name")

    submit = subparsers.add_parser("submit", add_help=False)
    submit.add_argument("mission_name")
    submit.add_argument("--to", required=True)
    submit.add_argument("--approved-by", action="append", default=[])
    submit.add_argument("--evidence-ref")

    return parser


def _render_status(console: Console, result: CertificationStatusResult) -> None:
    console.print(render_certification_status(result))


def _render_submit(console: Console, result: SubmitCertificationResult) -> None:
    console.print(render_certification_submission(result))
