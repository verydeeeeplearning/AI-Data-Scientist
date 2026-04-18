"""Terminal theme and styling constants."""

from rich.theme import Theme

DS_THEME = Theme(
    {
        "status.bar": "bold white on dark_blue",
        "status.mode.auto": "bold green",
        "status.mode.supervised": "bold yellow",
        "status.mode.step": "bold cyan",
        "tool.name": "bold yellow",
        "tool.done": "green",
        "tool.error": "red",
        "tool.time": "dim",
        "agent.thinking": "dim italic",
        "cost": "dim cyan",
        "user.prompt": "bold green",
        "heading": "bold cyan",
        "success": "bold green",
        "error": "bold red",
        "warning": "bold yellow",
        "muted": "dim",
    }
)

MODE_ICONS = {
    "auto": "[status.mode.auto]auto[/]",
    "supervised": "[status.mode.supervised]supervised[/]",
    "step-by-step": "[status.mode.step]step-by-step[/]",
}
