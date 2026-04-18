"""Verifier verdict CLI helpers."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from rich.console import Console

from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.domain.entities.shadow_comparison import ShadowComparisonRecord
from ds_agent.infrastructure.task_contract_container import build_task_contract_container
from ds_agent.infrastructure.verifier_container import build_verifier_container
from ds_agent.presentation.shadow_comparison_presenters import (
    render_shadow_comparison_report,
)
from ds_agent.presentation.verdict_presenters import (
    pick_effective_review_verdict,
    render_verdict_report,
)


def run_verdict_command(
    argv: Sequence[str],
    *,
    console: Console,
    workspace_dir: str | None,
    default_session_id: str | None = None,
) -> int:
    """Run `ds-agent verdict ...` or `/verdict`."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) or ["active"])

    if args.command == "active":
        verdict = _resolve_active_review_verdict(
            workspace_dir=workspace_dir,
            session_id=args.session_id or default_session_id,
            console=console,
        )
        if verdict is None:
            return 0
        console.print(render_verdict_report(verdict))
        return 0

    if args.command == "show":
        verdict = build_verifier_container(workspace_dir).repo.get(args.verdict_id)
        if verdict is None:
            console.print(f"Review verdict not found: {args.verdict_id}")
            return 1
        console.print(render_verdict_report(verdict))
        return 0

    if args.command == "shadow-active":
        record = _resolve_active_shadow_comparison(
            workspace_dir=workspace_dir,
            session_id=args.session_id or default_session_id,
            console=console,
        )
        if record is None:
            return 0
        console.print(render_shadow_comparison_report(record))
        return 0

    record = build_verifier_container(workspace_dir).shadow_repo.get(args.comparison_id)
    if record is None:
        console.print(f"Shadow comparison not found: {args.comparison_id}")
        return 1
    console.print(render_shadow_comparison_report(record))
    return 0


def show_active_review_verdict(
    *,
    console: Console,
    workspace_dir: str | None,
    session_id: str | None,
    argv: Sequence[str] | None = None,
) -> bool:
    """Print the latest review verdict for the current interactive session."""

    return run_verdict_command(
        argv or [],
        console=console,
        workspace_dir=workspace_dir,
        default_session_id=session_id,
    ) == 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ds-agent verdict", add_help=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    active = subparsers.add_parser("active", add_help=False)
    active.add_argument("--session-id")

    show = subparsers.add_parser("show", add_help=False)
    show.add_argument("verdict_id")

    shadow_active = subparsers.add_parser("shadow-active", add_help=False)
    shadow_active.add_argument("--session-id")

    shadow_show = subparsers.add_parser("shadow-show", add_help=False)
    shadow_show.add_argument("comparison_id")

    return parser


def _resolve_active_review_verdict(
    *,
    workspace_dir: str | None,
    session_id: str | None,
    console: Console,
) -> ReviewVerdict | None:
    if not session_id:
        console.print("Session id is required. Pass `--session-id` after the first run.")
        return None
    bundle = build_task_contract_container(workspace_dir).store.get_active_bundle(session_id)
    if bundle is None:
        console.print("No active task contract for this session.")
        return None
    verdict = pick_effective_review_verdict(bundle.review_verdicts)
    if verdict is None:
        console.print("No review verdict recorded for the active task contract.")
        return None
    return verdict


def _resolve_active_shadow_comparison(
    *,
    workspace_dir: str | None,
    session_id: str | None,
    console: Console,
) -> ShadowComparisonRecord | None:
    verdict = _resolve_active_review_verdict(
        workspace_dir=workspace_dir,
        session_id=session_id,
        console=console,
    )
    if verdict is None:
        return None
    record = _resolve_shadow_comparison_for_verdict(workspace_dir, verdict)
    if record is None:
        console.print("No shadow comparison recorded for the active verifier verdict.")
        return None
    return record


def _resolve_shadow_comparison_for_verdict(
    workspace_dir: str | None,
    verdict: ReviewVerdict,
) -> ShadowComparisonRecord | None:
    shadow_repo = build_verifier_container(workspace_dir).shadow_repo
    comparison_id = verdict.metadata.get("shadow_comparison_id")
    if isinstance(comparison_id, str) and comparison_id.strip():
        record = shadow_repo.get(comparison_id.strip())
        if record is not None:
            return record
    records = shadow_repo.list_for_verdict(verdict.verdict_id)
    return records[0] if records else None
