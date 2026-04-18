"""TUI component tests."""

from io import StringIO
from unittest.mock import patch

from rich.console import Console

from ds_agent.cli.commands import handle_slash_command
from ds_agent.cli.tui_callbacks import TUICallbacks, _truncate


class TestSlashCommands:
    def _make_console(self):
        return Console(file=StringIO(), force_terminal=True)

    def test_help_command(self):
        console = self._make_console()
        ctx: dict = {}
        result = handle_slash_command("/help", console, ctx)
        assert result is True

    def test_mode_cycle(self):
        console = self._make_console()
        ctx: dict = {"mode": "auto"}

        handle_slash_command("/mode", console, ctx)
        assert ctx["mode"] == "supervised"

        handle_slash_command("/mode", console, ctx)
        assert ctx["mode"] == "step-by-step"

        handle_slash_command("/mode", console, ctx)
        assert ctx["mode"] == "auto"

    def test_mode_set_explicit(self):
        console = self._make_console()
        ctx: dict = {"mode": "auto"}

        handle_slash_command("/mode supervised", console, ctx)
        assert ctx["mode"] == "supervised"

    def test_model_change(self):
        console = self._make_console()
        ctx: dict = {"model": "claude-sonnet-4"}

        handle_slash_command("/model openai/gpt-4.1", console, ctx)
        assert ctx["model"] == "openai/gpt-4.1"

    def test_quit_sets_flag(self):
        console = self._make_console()
        ctx: dict = {}

        handle_slash_command("/quit", console, ctx)
        assert ctx.get("should_exit") is True

    def test_status_command(self):
        console = self._make_console()
        ctx: dict = {"model": "test", "mode": "auto", "cost": 0.5, "steps": 3}

        result = handle_slash_command("/status", console, ctx)
        assert result is True

    def test_unknown_command(self):
        console = self._make_console()
        ctx: dict = {}

        result = handle_slash_command("/nonexistent", console, ctx)
        assert result is True  # Handled (with error message)

    def test_clear_command(self):
        console = self._make_console()
        ctx: dict = {}
        result = handle_slash_command("/clear", console, ctx)
        assert result is True

    def test_history_command(self):
        console = self._make_console()
        ctx: dict = {
            "history": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ]
        }
        result = handle_slash_command("/history", console, ctx)
        assert result is True

    def test_certification_command(self):
        console = self._make_console()
        ctx: dict = {"workspace_dir": "/workspace"}

        with patch(
            "ds_agent.cli.commands.show_certification_status",
            return_value=True,
        ) as mock_show:
            result = handle_slash_command("/certification weekly-kpi-triage", console, ctx)

        assert result is True
        mock_show.assert_called_once()


class TestTUICallbacks:
    def _make(self):
        console = Console(file=StringIO(), force_terminal=True)
        return TUICallbacks(console), console

    async def test_on_tool_start(self):
        cb, _console = self._make()
        await cb.on_tool_start("data_loader", {"file": "test.csv"})
        # Should not raise

    async def test_on_tool_end_success(self):
        cb, _console = self._make()
        cb._tool_start_time = 1000.0
        await cb.on_tool_end("data_loader", "result", is_error=False)

    async def test_on_tool_end_error(self):
        cb, _console = self._make()
        cb._tool_start_time = 1000.0
        await cb.on_tool_end("data_loader", "error", is_error=True)

    async def test_on_thinking(self):
        cb, console = self._make()
        await cb.on_thinking("This is a short thinking text")
        output = console.file.getvalue()
        assert "short thinking" in output

    async def test_on_thinking_long_text_truncated(self):
        cb, console = self._make()
        long_text = "A" * 200
        await cb.on_thinking(long_text)
        output = console.file.getvalue()
        assert "..." in output

    async def test_on_stream_delta(self):
        cb, console = self._make()
        await cb.on_stream_delta("hello")
        output = console.file.getvalue()
        assert "hello" in output

    async def test_on_status(self):
        cb, console = self._make()
        await cb.on_status("loading", "data.csv")
        output = console.file.getvalue()
        assert "loading" in output
        assert "data.csv" in output

    async def test_on_step(self):
        cb, _console = self._make()
        await cb.on_step(3, "Running EDA")
        assert cb._step_count == 3

    async def test_on_budget_warning_warning(self):
        from ds_agent.domain.value_objects.budget import BudgetThresholdEvent

        cb, console = self._make()
        event = BudgetThresholdEvent(
            dimension="cost",
            level="warning",
            used=8.0,
            limit=10.0,
            pct=80.0,
            message="Budget 80 pct used",
        )
        await cb.on_budget_warning(event)
        output = console.file.getvalue()
        assert "Budget" in output
        assert "80" in output

    async def test_on_budget_warning_critical(self):
        from ds_agent.domain.value_objects.budget import BudgetThresholdEvent

        cb, console = self._make()
        event = BudgetThresholdEvent(
            dimension="cost",
            level="critical",
            used=9.5,
            limit=10.0,
            pct=95.0,
            message="Budget 95 pct used",
        )
        await cb.on_budget_warning(event)
        output = console.file.getvalue()
        assert "Budget" in output
        assert "95" in output

    async def test_on_budget_warning_exhausted(self):
        from ds_agent.domain.value_objects.budget import BudgetThresholdEvent

        cb, console = self._make()
        event = BudgetThresholdEvent(
            dimension="cost",
            level="exhausted",
            used=10.0,
            limit=10.0,
            pct=100.0,
            message="Budget exhausted now",
        )
        await cb.on_budget_warning(event)
        output = console.file.getvalue()
        assert "exhausted" in output.lower()


class TestTruncate:
    def test_short_string_unchanged(self):
        assert _truncate("hello", max_len=40) == "hello"

    def test_long_string_truncated(self):
        result = _truncate("A" * 50, max_len=40)
        assert len(result) == 43  # 40 + "..."
        assert result.endswith("...")

    def test_exact_length_unchanged(self):
        assert _truncate("A" * 40, max_len=40) == "A" * 40
