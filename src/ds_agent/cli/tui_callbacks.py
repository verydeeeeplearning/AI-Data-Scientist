"""TUI callbacks — Rich-based interactive terminal display."""

from __future__ import annotations

import time

from rich.console import Console

from ds_agent.domain.value_objects.budget import BudgetThresholdEvent


class TUICallbacks:
    """Interactive TUI callbacks for the agent loop.

    Renders:
    - Tool activity (name, running/done, elapsed time)
    - Streaming LLM tokens
    - Budget warnings
    - Status updates
    """

    def __init__(self, console: Console) -> None:
        self.console = console
        self._tool_start_time: float = 0
        self._step_count: int = 0
        self._total_cost: float = 0.0

    async def on_tool_start(self, tool_name: str, arguments: dict) -> None:
        self._tool_start_time = time.monotonic()
        args_short = ", ".join(f"{k}={_truncate(str(v))}" for k, v in arguments.items())
        self.console.print(f"  [tool.name]▶ {tool_name}[/]({args_short})", end="")

    async def on_tool_end(self, tool_name: str, result: str, is_error: bool) -> None:
        elapsed = time.monotonic() - self._tool_start_time
        if is_error:
            self.console.print(f" [tool.error]✗[/] [tool.time]{elapsed:.1f}s[/]")
        else:
            self.console.print(f" [tool.done]✓[/] [tool.time]{elapsed:.1f}s[/]")

    async def on_thinking(self, thinking_text: str) -> None:
        # Show truncated thinking
        short = thinking_text[:100] + "..." if len(thinking_text) > 100 else thinking_text
        self.console.print(f"  [agent.thinking]{short}[/]")

    async def on_stream_delta(self, delta: str) -> None:
        self.console.print(delta, end="")

    async def on_step(self, step_num: int, message: str) -> None:
        self._step_count = step_num

    async def on_status(self, status: str, detail: str) -> None:
        self.console.print(f"  [muted]{status}: {detail}[/]")

    async def on_budget_warning(self, event: BudgetThresholdEvent) -> None:
        if event.level == "warning":
            self.console.print(f"  [warning]⚠ {event.message}[/]")
        elif event.level == "critical":
            self.console.print(f"  [error]⚠ {event.message}[/]")
        elif event.level == "exhausted":
            self.console.print(f"  [error]✗ {event.message}[/]")


def _truncate(s: str, max_len: int = 40) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."
