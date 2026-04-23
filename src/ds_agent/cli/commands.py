"""Slash command handlers for the interactive TUI plus deep-link subcommands."""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Sequence
from typing import Final

from rich.console import Console
from rich.table import Table

from ds_agent.cli.certification_cli import show_certification_status
from ds_agent.cli.task_contract_cli import show_active_task_contract
from ds_agent.cli.verdict_cli import show_active_review_verdict
from ds_agent.domain.value_objects.deep_link import (
    DEEP_LINK_RESOURCE_TYPES,
    DeepLink,
    DeepLinkParseError,
    build_deep_link_uri,
    parse_deep_link,
)

HELP_TEXT = """\
[bold]Slash Commands[/]
  /help          Show this help
  /mode          Switch mode (auto / supervised / step-by-step)
  /status        Show project status, cost, steps
  /files         List generated artifacts
  /model <name>  Change LLM model
  /budget        Show budget usage
  /contract      Show the active task contract for this session
  /certification Show mission certification status
  /verdict [show <id>|shadow [comparison_id]]
                Show verifier verdict or shadow diff for this session
  /history       Show conversation history (last 10)
  /clear         Clear screen
  /quit          Exit ds-agent

[bold]Keyboard[/]
  Ctrl+C         Interrupt current agent operation
  Ctrl+D         Exit ds-agent
"""


def handle_slash_command(
    command: str,
    console: Console,
    context: dict,
) -> bool:
    """Handle a slash command. Returns True if handled, False otherwise."""
    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "/help":
        console.print(HELP_TEXT)
        return True

    if cmd == "/mode":
        return _handle_mode(arg, console, context)

    if cmd == "/status":
        return _handle_status(console, context)

    if cmd == "/files":
        return _handle_files(console, context)

    if cmd == "/model":
        if arg:
            context["model"] = arg
            console.print(f"  Model changed to [bold]{arg}[/]")
        else:
            console.print(f"  Current model: [bold]{context.get('model', 'unknown')}[/]")
        return True

    if cmd == "/budget":
        return _handle_budget(console, context)

    if cmd == "/contract":
        return show_active_task_contract(
            console=console,
            workspace_dir=context.get("workspace_dir"),
            session_id=context.get("session_id"),
        )

    if cmd == "/certification":
        return show_certification_status(
            console=console,
            workspace_dir=context.get("workspace_dir"),
            mission_name=arg.strip() or None,
        )

    if cmd == "/verdict":
        return show_active_review_verdict(
            console=console,
            workspace_dir=context.get("workspace_dir"),
            session_id=context.get("session_id"),
            argv=arg.split() if arg.strip() else None,
        )

    if cmd == "/clear":
        console.clear()
        return True

    if cmd in ("/quit", "/exit", "/q"):
        context["should_exit"] = True
        return True

    if cmd == "/history":
        history = context.get("history", [])
        for msg in history[-10:]:
            role = msg.get("role", "?")
            content = msg.get("content", "")[:80]
            console.print(f"  [{role}] {content}")
        if not history:
            console.print("  [muted]No history yet[/]")
        return True

    console.print(f"  [error]Unknown command: {cmd}[/]. Type /help for available commands.")
    return True


def _handle_mode(arg: str, console: Console, context: dict) -> bool:
    modes = ["auto", "supervised", "step-by-step"]
    if arg in modes:
        context["mode"] = arg
        console.print(f"  Mode: [bold]{arg}[/]")
    elif arg:
        console.print(f"  [error]Invalid mode.[/] Options: {', '.join(modes)}")
    else:
        current = context.get("mode", "auto")
        # Cycle to next mode
        idx = modes.index(current) if current in modes else 0
        next_mode = modes[(idx + 1) % len(modes)]
        context["mode"] = next_mode
        console.print(f"  Mode: [bold]{next_mode}[/]")
    return True


def _handle_status(console: Console, context: dict) -> bool:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Model", context.get("model", "not set"))
    table.add_row("Mode", context.get("mode", "auto"))
    table.add_row("Project", context.get("project_id", "none"))
    table.add_row("Steps", str(context.get("steps", 0)))
    table.add_row("Tool calls", str(context.get("tool_calls", 0)))
    table.add_row("Cost", f"${context.get('cost', 0):.4f}")
    console.print(table)
    return True


def _handle_files(console: Console, context: dict) -> bool:
    files = context.get("artifacts", [])
    if not files:
        console.print("  [muted]No artifacts generated yet[/]")
    else:
        for f in files:
            console.print(f"  {f}")
    return True


def _handle_budget(console: Console, context: dict) -> bool:
    budget = context.get("budget_summary", {})
    if not budget:
        console.print("  [muted]No budget data yet[/]")
    else:
        for key, val in budget.items():
            console.print(f"  {key}: {val}")
    return True


# --------------------------------------------------------------------------- #
# Deep link subcommands (PLAN_03 sp3.3) — `ds-agent open` / `ds-agent share`. #
# --------------------------------------------------------------------------- #

OPEN_USAGE: Final[str] = "Usage: ds-agent open <ds-agent://...>"
SHARE_USAGE: Final[str] = (
    "Usage: ds-agent share <resource_type> <resource_id> [--workspace <id>] [--action <name>]"
)
DEFAULT_WORKSPACE_ID: Final[str] = "default"


def _format_parse_error(error: DeepLinkParseError | None) -> str:
    return (error.value if error is not None else "unknown_error").replace("_", " ")


def run_open_command(
    argv: Sequence[str],
    *,
    console: Console | None = None,
    launcher: object | None = None,
) -> int:
    """Handle ``ds-agent open <url>``.

    Validates the URI through the domain parser **before** any side effect, then
    asks the OS to launch the registered ``ds-agent://`` handler (Electron).

    ``launcher`` (testing hook): a callable ``(uri: str) -> int`` that replaces
    the default OS-specific launcher.
    """

    out = console or Console()
    if len(argv) != 1:
        out.print(f"  [error]{OPEN_USAGE}[/]")
        return 2

    uri = argv[0].strip()
    parse_result = parse_deep_link(uri)
    if not parse_result.ok:
        out.print(f"  [error]Invalid deep link[/]: {_format_parse_error(parse_result.error)}")
        return 1

    try:
        rc = (launcher or _launch_protocol_handler)(uri)  # type: ignore[operator]
    except Exception as exc:  # pragma: no cover - defensive
        out.print(f"  [error]Failed to launch handler[/]: {exc}")
        return 1
    if isinstance(rc, int) and rc != 0:
        out.print(f"  [warning]Handler exited with code {rc}[/]")
        return rc
    out.print(f"  [success]Opened[/] {uri}")
    return 0


def run_share_command(
    argv: Sequence[str],
    *,
    console: Console | None = None,
    default_workspace_id: str = DEFAULT_WORKSPACE_ID,
    clipboard: object | None = None,
) -> int:
    """Handle ``ds-agent share <type> <id> [--workspace W] [--action A]``.

    Builds a wire-format URI and copies it to the clipboard (best-effort —
    falls back to plain print if ``pyperclip`` is unavailable).

    ``clipboard`` (testing hook): callable ``(text: str) -> bool`` that replaces
    the default ``pyperclip`` adapter. Returning ``True`` means "copied".
    """

    out = console or Console()
    parsed = _parse_share_args(argv)
    if parsed is None:
        out.print(f"  [error]{SHARE_USAGE}[/]")
        out.print(f"  [muted]resource_type ∈ {list(DEEP_LINK_RESOURCE_TYPES)}[/]")
        return 2

    resource_type, resource_id, workspace_id, action = parsed
    if workspace_id is None:
        workspace_id = default_workspace_id

    link = DeepLink(
        workspace_id=workspace_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
    )
    uri = build_deep_link_uri(link)

    # Re-parse so any malformed user input is rejected with the same error
    # vocabulary as `ds-agent open`. Shares MUST round-trip through the parser.
    verify = parse_deep_link(uri)
    if not verify.ok:
        out.print(f"  [error]Refusing to share[/]: {_format_parse_error(verify.error)}")
        return 1

    copied = False
    try:
        copy = clipboard if clipboard is not None else _copy_to_clipboard
        copied = bool(copy(uri))  # type: ignore[operator]
    except Exception:
        copied = False

    out.print(uri)
    if copied:
        out.print("  [muted](copied to clipboard)[/]")
    else:
        out.print("  [muted](clipboard unavailable — pip install pyperclip)[/]")
    return 0


def _parse_share_args(
    argv: Sequence[str],
) -> tuple[str, str, str | None, str | None] | None:
    """Tiny argparse-free flag parser to keep the subcommand self-contained.

    Returns ``(resource_type, resource_id, workspace_id, action)`` or ``None``
    when the args do not match the expected shape.
    """

    if len(argv) < 2:
        return None

    positional: list[str] = []
    workspace_id: str | None = None
    action: str | None = None

    i = 0
    while i < len(argv):
        token = argv[i]
        if token == "--workspace":
            if i + 1 >= len(argv):
                return None
            workspace_id = argv[i + 1]
            i += 2
            continue
        if token == "--action":
            if i + 1 >= len(argv):
                return None
            action = argv[i + 1]
            i += 2
            continue
        if token.startswith("--"):
            return None
        positional.append(token)
        i += 1

    if len(positional) != 2:
        return None
    return positional[0], positional[1], workspace_id, action


def _launch_protocol_handler(uri: str) -> int:
    """Open ``uri`` with the OS-registered protocol handler.

    Branches on platform:
      * Windows → ``cmd /c start "" "<uri>"`` (the empty title slot is
        required so ``start`` does not consume the URI as a window title).
      * macOS   → ``open "<uri>"``
      * Linux   → ``xdg-open "<uri>"``
    """

    if sys.platform.startswith("win"):
        # ``shell=True`` lets ``start`` resolve correctly; the URI is already
        # validated by `parse_deep_link`, so injection risk is bounded.
        return subprocess.call(
            ["cmd", "/c", "start", "", uri],
            shell=False,
        )
    if sys.platform == "darwin":
        return subprocess.call(["open", uri])
    # Assume xdg-compatible (Linux / *BSD).
    opener = shutil.which("xdg-open") or "xdg-open"
    return subprocess.call([opener, uri])


def _copy_to_clipboard(text: str) -> bool:
    """Best-effort clipboard copy using ``pyperclip`` if installed."""

    try:
        import pyperclip  # type: ignore[import-not-found,import-untyped]
    except ImportError:
        return False
    try:
        pyperclip.copy(text)
        return True
    except Exception:
        return False
