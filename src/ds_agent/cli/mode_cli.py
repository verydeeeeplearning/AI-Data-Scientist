"""CLI helpers for incident/freeze authority overlays."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from ds_agent.api.config_manager import ConfigManager
from ds_agent.config.loader import get_default_config_path
from ds_agent.config.schema import DSAgentConfig
from ds_agent.runtime.authority_overlay import (
    effective_authority_mode,
    new_incident_started_at,
    resolve_authority_overlay,
)
from ds_agent.runtime.legacy_mode_migration import build_legacy_mode_migration_preview

_USAGE = (
    "Usage: ds-agent mode status | migrate [legacy-mode] | incident start|end | freeze [start|end]"
)


def run_mode_command(
    args: list[str],
    *,
    console: Console,
    config_path: str | Path | None = None,
    config: DSAgentConfig | None = None,
) -> int:
    """Run the authority overlay management CLI."""

    resolved_path = Path(config_path) if config_path is not None else get_default_config_path()
    manager = ConfigManager(config=config, config_path=resolved_path)
    _clear_expired_overlay(manager)

    if not args or args[0] in {"status", "show"}:
        _print_status(console, manager.config)
        return 0

    command = str(args[0]).strip().lower()
    action = str(args[1]).strip().lower() if len(args) > 1 else "start"

    if command == "migrate":
        target_mode = args[1] if len(args) > 1 else manager.config.agent.mode
        _print_migration_preview(console, target_mode)
        return 0

    if command == "incident":
        if action == "start":
            manager.set("gateway.authority_overlay", "incident")
            manager.set("gateway.authority_overlay_started_at", new_incident_started_at())
            _print_status(console, manager.config, message="Incident overlay activated.")
            return 0
        if action in {"end", "stop", "clear"}:
            _clear_overlay(manager)
            _print_status(console, manager.config, message="Authority overlay cleared.")
            return 0
    elif command == "freeze":
        if action == "start":
            manager.set("gateway.authority_overlay", "freeze")
            manager.set("gateway.authority_overlay_started_at", None)
            _print_status(console, manager.config, message="Freeze overlay activated.")
            return 0
        if action in {"end", "stop", "clear"}:
            _clear_overlay(manager)
            _print_status(console, manager.config, message="Authority overlay cleared.")
            return 0

    console.print(f"[error]{_USAGE}[/]")
    return 1


def _print_status(console: Console, config: DSAgentConfig, *, message: str | None = None) -> None:
    overlay = resolve_authority_overlay(
        getattr(config.gateway, "authority_overlay", None),
        getattr(config.gateway, "authority_overlay_started_at", None),
    )
    effective = effective_authority_mode(
        legacy_mode=config.agent.mode,
        overlay_mode=getattr(config.gateway, "authority_overlay", None),
        overlay_started_at=getattr(config.gateway, "authority_overlay_started_at", None),
    )
    if message:
        console.print(f"[bold cyan]{message}[/]")
    console.print(
        f"Authority overlay: [bold]{overlay.mode.value if overlay.mode is not None else 'none'}[/]"
    )
    console.print(f"Effective authority mode: [bold]{effective.value}[/]")
    console.print(f"Legacy mode: [bold]{config.agent.mode}[/]")
    if overlay.started_at is not None:
        console.print(f"Started at: {overlay.started_at.isoformat()}")
    if overlay.expires_at is not None:
        console.print(f"Expires at: {overlay.expires_at.isoformat()}")


def _print_migration_preview(console: Console, legacy_mode: str | None) -> None:
    preview = build_legacy_mode_migration_preview(legacy_mode)
    console.print("[bold cyan]Legacy mode migration preview[/]")
    console.print(f"Legacy mode: [bold]{preview.legacy_mode}[/]")
    console.print(f"Recommended authority: [bold]{preview.authority.value}[/]")
    console.print(f"Recommended audience: [bold]{preview.audience.value}[/]")
    console.print("Mapping: [bold]" + ("exact" if preview.exact_match else "approximate") + "[/]")
    console.print("Follow-up:")
    for note in preview.notes:
        console.print(f"- {note}")


def _clear_expired_overlay(manager: ConfigManager) -> None:
    overlay = resolve_authority_overlay(
        getattr(manager.config.gateway, "authority_overlay", None),
        getattr(manager.config.gateway, "authority_overlay_started_at", None),
    )
    if overlay.expired:
        _clear_overlay(manager)


def _clear_overlay(manager: ConfigManager) -> None:
    manager.set("gateway.authority_overlay", None)
    manager.set("gateway.authority_overlay_started_at", None)
