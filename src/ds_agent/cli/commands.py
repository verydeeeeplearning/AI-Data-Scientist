"""Slash command handlers for the interactive TUI."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from ds_agent.cli.certification_cli import show_certification_status
from ds_agent.cli.task_contract_cli import show_active_task_contract
from ds_agent.cli.verdict_cli import show_active_review_verdict

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
