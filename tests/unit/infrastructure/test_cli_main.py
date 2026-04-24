"""Tests for cli/main.py (Phase 7)."""

from __future__ import annotations

from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from ds_agent.agent.factory import import_all_tools
from ds_agent.cli.main import _create_provider, _print_banner, _print_status_line
from ds_agent.config.schema import DSAgentConfig, OAuthConfig, ProviderConfig


class TestPrintBanner:
    def test_renders_without_crash(self):
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)
        _print_banner(console, "claude-sonnet-4-6", "auto")
        output = out.getvalue()
        assert len(output) > 0

    def test_contains_model_name(self):
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)
        _print_banner(console, "gpt-5.4", "supervised")
        output = out.getvalue()
        assert "gpt-5.4" in output


class TestPrintStatusLine:
    def test_renders_without_crash(self):
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)
        _print_status_line(console, {"mode": "auto", "cost": 0.05})
        output = out.getvalue()
        assert len(output) > 0

    def test_shows_cost(self):
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)
        _print_status_line(console, {"mode": "auto", "cost": 1.2345})
        output = out.getvalue()
        assert "1.2345" in output


class TestCreateProvider:
    def test_success_returns_router(self):
        mock_router = MagicMock()
        with patch("ds_agent.providers.router.ProviderRouter", return_value=mock_router):
            provider = _create_provider("anthropic/claude-sonnet-4-6")
        assert provider is mock_router

    def test_uses_shared_runtime_factory_when_config_is_provided(self, tmp_path):
        config = DSAgentConfig(
            provider=ProviderConfig(),
            oauth=OAuthConfig(token_store_path=str(tmp_path / "auth_profiles.json")),
        )
        token_store = MagicMock()
        mock_provider = MagicMock()

        with patch(
            "ds_agent.cli.main.create_provider_router",
            return_value=mock_provider,
        ) as mock_factory:
            provider = _create_provider(
                "gemini/gemini-2.5-pro",
                config=config,
                token_store=token_store,
            )

        assert provider is mock_provider
        mock_factory.assert_called_once_with(
            "gemini/gemini-2.5-pro",
            config,
            token_store=token_store,
        )

    def test_fallback_on_error(self):
        with patch(
            "ds_agent.providers.router.ProviderRouter",
            side_effect=Exception("No API key"),
        ):
            provider = _create_provider("anthropic/claude-sonnet-4-6")
        # Should return a stub mock provider, not raise
        assert provider is not None
        assert hasattr(provider, "chat")


class TestRunAgentTurn:
    @pytest.mark.asyncio
    async def test_success(self):
        from ds_agent.cli.main import _run_agent_turn

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Analysis complete.")
        mock_agent._budget = MagicMock()
        mock_agent._budget.get_summary.return_value = {
            "total_cost_usd": 0.01,
            "iterations_used": 3,
        }

        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)
        context = {"_agent": mock_agent, "mode": "auto", "cost": 0}

        await _run_agent_turn("Analyze this", console, context)

        mock_agent.run.assert_called_once_with("Analyze this")

    @pytest.mark.asyncio
    async def test_error_handled(self):
        from ds_agent.cli.main import _run_agent_turn

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=RuntimeError("LLM down"))

        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)
        context = {"_agent": mock_agent, "mode": "auto", "cost": 0}

        await _run_agent_turn("Analyze this", console, context)
        output = out.getvalue()
        assert "Error" in output or "error" in output

    @pytest.mark.asyncio
    async def test_none_result(self):
        """Agent returning None should not crash."""
        from ds_agent.cli.main import _run_agent_turn

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=None)

        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)
        context = {"_agent": mock_agent, "mode": "auto", "cost": 0}

        await _run_agent_turn("Hello", console, context)
        # Should not crash, steps should increment
        assert context.get("steps", 0) >= 1

    @pytest.mark.asyncio
    async def test_updates_cost_from_budget(self):
        """After a run, context should update cost from agent budget."""
        from ds_agent.cli.main import _run_agent_turn

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Done.")
        mock_agent._budget = MagicMock()
        mock_agent._budget.get_summary.return_value = {
            "total_cost_usd": 0.05,
            "iterations_used": 5,
        }

        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)
        context = {"_agent": mock_agent, "mode": "auto", "cost": 0}

        await _run_agent_turn("Analyze", console, context)
        assert context["cost"] == 0.05
        assert context["tool_calls"] == 5


class TestCreateProviderEdgeCases:
    def test_fallback_provider_has_required_methods(self):
        """The fallback stub provider should have chat, count_tokens, get_model_info."""
        with patch(
            "ds_agent.providers.router.ProviderRouter",
            side_effect=Exception("No key"),
        ):
            provider = _create_provider("anthropic/claude-sonnet-4")
        assert hasattr(provider, "chat")
        assert hasattr(provider, "count_tokens")
        assert hasattr(provider, "get_model_info")

        info = provider.get_model_info()
        assert info.model_id == "anthropic/claude-sonnet-4"

    def test_router_success_various_models(self):
        """_create_provider should accept different model strings."""
        for model in ["openai/gpt-4.1", "groq/llama-3.3-70b", "claude-sonnet-4"]:
            mock_router = MagicMock()
            with patch("ds_agent.providers.router.ProviderRouter", return_value=mock_router):
                provider = _create_provider(model)
            assert provider is mock_router


class TestPrintStatusLineEdgeCases:
    def test_with_project_id(self):
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)
        _print_status_line(console, {"mode": "auto", "cost": 0.0, "project_id": "my-project"})
        output = out.getvalue()
        assert "my-project" in output

    def test_no_project_id(self):
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)
        _print_status_line(console, {"mode": "auto", "cost": 0.0})
        output = out.getvalue()
        assert len(output) > 0


class TestMain:
    def test_main_version(self):
        """ds-agent --version should print version and exit."""
        import sys
        from unittest.mock import patch as _patch

        from ds_agent.cli.main import main

        with (
            _patch.object(sys, "argv", ["ds-agent", "--version"]),
            _patch("builtins.print") as mock_print,
        ):
            main()
            mock_print.assert_called_once()
            assert "v0.1.0" in mock_print.call_args[0][0]

    def test_main_version_subcmd(self):
        """ds-agent version should print version."""
        import sys
        from unittest.mock import patch as _patch

        from ds_agent.cli.main import main

        with (
            _patch.object(sys, "argv", ["ds-agent", "version"]),
            _patch("builtins.print") as mock_print,
        ):
            main()
            assert "v0.1.0" in mock_print.call_args[0][0]

    def test_main_init_subcommand(self):
        """ds-agent init should call run_onboard."""
        import sys
        from unittest.mock import patch as _patch

        from ds_agent.cli.main import main

        with (
            _patch.object(sys, "argv", ["ds-agent", "init"]),
            _patch("ds_agent.cli.main.Console"),
            _patch("ds_agent.cli.wizard.onboard.run_onboard") as mock_onboard,
        ):
            main()
            mock_onboard.assert_called_once()

    def test_main_one_shot_mode(self):
        """ds-agent 'message' should run one-shot."""
        import sys
        from unittest.mock import patch as _patch

        from ds_agent.cli.main import main

        with (
            _patch.object(sys, "argv", ["ds-agent", "hello", "world"]),
            _patch("ds_agent.cli.main.Console"),
            _patch("ds_agent.cli.main.load_config") as mock_config,
            _patch("ds_agent.cli.main.asyncio") as mock_asyncio,
        ):
            mock_cfg = MagicMock()
            mock_cfg.provider.default_model = "claude-sonnet-4-6"
            mock_cfg.agent.mode = "auto"
            mock_cfg.agent.max_iterations = 100
            mock_cfg.provider.max_budget_usd = 10.0
            mock_config.return_value = mock_cfg
            mock_asyncio.run.side_effect = lambda coro: coro.close()
            main()
            mock_asyncio.run.assert_called_once()

    def test_main_contract_subcommand(self):
        """ds-agent contract ... should dispatch to the task-contract CLI."""
        import sys
        from unittest.mock import patch as _patch

        from ds_agent.cli.main import main

        with (
            _patch.object(sys, "argv", ["ds-agent", "contract", "list"]),
            _patch("ds_agent.cli.main.Console"),
            _patch("ds_agent.cli.main.load_config") as mock_config,
            _patch("ds_agent.cli.main.run_contract_command") as mock_contract,
        ):
            mock_cfg = MagicMock()
            mock_cfg.agent.workspace_dir = "C:/workspace"
            mock_config.return_value = mock_cfg

            main()

            mock_contract.assert_called_once()
            assert mock_contract.call_args.args[0] == ["list"]
            assert mock_contract.call_args.kwargs["workspace_dir"] == "C:/workspace"

    def test_main_certification_subcommand(self):
        """ds-agent certification ... should dispatch to the certification CLI."""
        import sys
        from unittest.mock import patch as _patch

        from ds_agent.cli.main import main

        with (
            _patch.object(
                sys,
                "argv",
                ["ds-agent", "certification", "status", "weekly-kpi-triage"],
            ),
            _patch("ds_agent.cli.main.Console"),
            _patch("ds_agent.cli.main.load_config") as mock_config,
            _patch("ds_agent.cli.main.run_certification_command") as mock_certification,
        ):
            mock_cfg = MagicMock()
            mock_cfg.agent.workspace_dir = "C:/workspace"
            mock_config.return_value = mock_cfg

            main()

            mock_certification.assert_called_once()
            assert mock_certification.call_args.args[0] == ["status", "weekly-kpi-triage"]
            assert mock_certification.call_args.kwargs["workspace_dir"] == "C:/workspace"

    def test_main_semantic_subcommand(self):
        """ds-agent semantic ... should dispatch to the semantic CLI."""
        import sys
        from unittest.mock import patch as _patch

        from ds_agent.cli.main import main

        with (
            _patch.object(sys, "argv", ["ds-agent", "semantic", "lookup", "churn"]),
            _patch("ds_agent.cli.main.Console"),
            _patch("ds_agent.cli.main.load_config") as mock_config,
            _patch("ds_agent.cli.main.run_semantic_command") as mock_semantic,
        ):
            mock_cfg = MagicMock()
            mock_cfg.agent.workspace_dir = "C:/workspace"
            mock_config.return_value = mock_cfg

            with pytest.raises(SystemExit):
                main()

            mock_semantic.assert_called_once()
            assert mock_semantic.call_args.args[0] == ["lookup", "churn"]
            assert mock_semantic.call_args.kwargs["workspace_dir"] == "C:/workspace"

    def test_main_mode_subcommand(self):
        """ds-agent mode ... should dispatch to the mode CLI."""
        import sys
        from unittest.mock import patch as _patch

        from ds_agent.cli.main import main

        with (
            _patch.object(sys, "argv", ["ds-agent", "mode", "incident", "start"]),
            _patch("ds_agent.cli.main.Console"),
            _patch("ds_agent.cli.main.load_config") as mock_config,
            _patch("ds_agent.cli.main.run_mode_command", return_value=0) as mock_mode,
        ):
            mock_cfg = MagicMock()
            mock_config.return_value = mock_cfg

            with pytest.raises(SystemExit) as excinfo:
                main()

            assert excinfo.value.code == 0
            mock_mode.assert_called_once()
            assert mock_mode.call_args.args[0] == ["incident", "start"]

    def test_main_work_subcommand(self):
        """ds-agent work ... should dispatch to the work CLI."""
        import sys
        from unittest.mock import patch as _patch

        from ds_agent.cli.main import main

        with (
            _patch.object(sys, "argv", ["ds-agent", "work", "list", "--limit", "5"]),
            _patch("ds_agent.cli.main.Console"),
            _patch("ds_agent.cli.main.load_config") as mock_config,
            _patch("ds_agent.cli.main.run_work_command", return_value=0) as mock_work,
        ):
            mock_cfg = MagicMock()
            mock_cfg.agent.workspace_dir = "C:/workspace"
            mock_config.return_value = mock_cfg

            with pytest.raises(SystemExit) as excinfo:
                main()

            assert excinfo.value.code == 0
            mock_work.assert_called_once()
            assert mock_work.call_args.args[0] == ["list", "--limit", "5"]
            assert mock_work.call_args.kwargs["workspace_dir"] == "C:/workspace"


class TestImportTools:
    def test_import_tools_no_crash(self):
        """import_all_tools should import all tool modules without error."""
        import_all_tools()


class TestInteractiveLoop:
    def test_interactive_loop_exit_on_eof(self):
        """interactive_loop should exit gracefully on EOFError."""
        from ds_agent.cli.main import interactive_loop

        with (
            patch("ds_agent.cli.main.Console") as mock_console_cls,
            patch("ds_agent.cli.main.load_config") as mock_config,
            patch("ds_agent.cli.main._print_banner"),
        ):
            mock_cfg = MagicMock()
            mock_cfg.provider.default_model = "claude-sonnet-4-6"
            mock_cfg.agent.mode = "auto"
            mock_cfg.agent.max_iterations = 100
            mock_cfg.provider.max_budget_usd = 10.0
            mock_config.return_value = mock_cfg

            mock_console = MagicMock()
            mock_console.input = MagicMock(side_effect=EOFError)
            mock_console_cls.return_value = mock_console

            interactive_loop()
            # Should have called input at least once
            mock_console.input.assert_called()

    def test_interactive_loop_empty_input_skipped(self):
        """Empty input lines should be skipped."""
        from ds_agent.cli.main import interactive_loop

        with (
            patch("ds_agent.cli.main.Console") as mock_console_cls,
            patch("ds_agent.cli.main.load_config") as mock_config,
            patch("ds_agent.cli.main._print_banner"),
        ):
            mock_cfg = MagicMock()
            mock_cfg.provider.default_model = "claude-sonnet-4-6"
            mock_cfg.agent.mode = "auto"
            mock_cfg.agent.max_iterations = 100
            mock_cfg.provider.max_budget_usd = 10.0
            mock_config.return_value = mock_cfg

            mock_console = MagicMock()
            # First return empty, then KeyboardInterrupt to exit
            mock_console.input = MagicMock(side_effect=["", KeyboardInterrupt()])
            mock_console_cls.return_value = mock_console

            interactive_loop()
            # Should have called input twice (once empty, once KeyboardInterrupt)
            assert mock_console.input.call_count == 2

    def test_interactive_loop_slash_command(self):
        """Slash commands should be routed to handle_slash_command."""
        from ds_agent.cli.main import interactive_loop

        with (
            patch("ds_agent.cli.main.Console") as mock_console_cls,
            patch("ds_agent.cli.main.load_config") as mock_config,
            patch("ds_agent.cli.main._print_banner"),
            patch("ds_agent.cli.main.handle_slash_command") as mock_slash,
        ):
            mock_cfg = MagicMock()
            mock_cfg.provider.default_model = "claude-sonnet-4-6"
            mock_cfg.agent.mode = "auto"
            mock_cfg.agent.max_iterations = 100
            mock_cfg.provider.max_budget_usd = 10.0
            mock_config.return_value = mock_cfg

            mock_console = MagicMock()
            mock_console.input = MagicMock(side_effect=["/help", EOFError])
            mock_console_cls.return_value = mock_console

            interactive_loop()
            mock_slash.assert_called_once()
