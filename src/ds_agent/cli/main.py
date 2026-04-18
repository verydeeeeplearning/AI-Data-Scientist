"""DS Agent — Interactive Terminal Application.

Claude Code-style interactive TUI for data science.
LLM renders results as markdown, Rich renders markdown beautifully.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import Awaitable, Callable

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from ds_agent.cli.certification_cli import run_certification_command
from ds_agent.cli.commands import handle_slash_command
from ds_agent.cli.delivery_cli import run_delivery_command
from ds_agent.cli.integration_cli import run_integration_command
from ds_agent.cli.learning_cli import run_learning_command
from ds_agent.cli.mode_cli import run_mode_command
from ds_agent.cli.portfolio_cli import run_portfolio_command
from ds_agent.cli.semantic_cli import run_semantic_command
from ds_agent.cli.task_contract_cli import run_contract_command
from ds_agent.cli.theme import DS_THEME, MODE_ICONS
from ds_agent.cli.tui_callbacks import TUICallbacks
from ds_agent.cli.verdict_cli import run_verdict_command
from ds_agent.cli.work_cli import run_work_command
from ds_agent.config.loader import get_default_config_path, load_config
from ds_agent.config.schema import DSAgentConfig
from ds_agent.domain.entities.messages import ChatMessage, LLMResponse, Usage
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.domain.interfaces.llm_provider import LLMProvider
from ds_agent.infrastructure.auth.token_store import AuthProfileStore
from ds_agent.runtime.authority_overlay import resolve_authority_overlay
from ds_agent.runtime.checkpoint_store import JsonCheckpointStore
from ds_agent.runtime.provider_factory import create_auth_profile_store, create_provider_router
from ds_agent.runtime.transcript_store import JsonTranscriptStore


def _print_banner(console: Console, config_model: str, mode: str) -> None:
    mode_display = MODE_ICONS.get(mode, mode)
    banner = Text.from_markup(
        f"[bold cyan]DS Agent[/] v0.1.0  │  "
        f"Model: [bold]{config_model}[/]  │  "
        f"Mode: {mode_display}  │  "
        f"[muted]/help for commands[/]"
    )
    console.print(Panel(banner, border_style="cyan", padding=(0, 1)))
    _print_secret_storage_warning(console)
    console.print()


def _print_secret_storage_warning(console: Console) -> None:
    """Warn the operator when secrets are not persisted across restarts."""
    from ds_agent.infrastructure.secrets import describe_secret_storage

    status = describe_secret_storage()
    if not status.get("degraded"):
        return
    console.print(
        Panel(
            Text.from_markup(f"[bold yellow]⚠ Secrets in volatile storage[/]\n{status['message']}"),
            border_style="yellow",
            padding=(0, 1),
        )
    )


def _print_status_line(console: Console, context: dict) -> None:
    mode_display = MODE_ICONS.get(context.get("mode", "auto"), "auto")
    project = context.get("project_id", "")
    cost = context.get("cost", 0)
    project_part = f" │ {project}" if project else ""
    console.print(f"[muted]─── {mode_display}{project_part} │ ${cost:.4f} ───[/]")


async def _run_agent_turn(
    user_input: str,
    console: Console,
    context: dict,
) -> None:
    """Run one agent turn: send message → display tool activity → render response."""
    # Lazy import to avoid circular deps and allow running without provider SDKs
    from ds_agent.agent.factory import create_agent

    callbacks = TUICallbacks(console)

    # Get or create agent
    agent = context.get("_agent")
    if agent is None:
        # Create a mock provider for now (real providers need API keys)
        model_str = context.get("model", "anthropic/claude-sonnet-4-6")
        session_id = context.setdefault("session_id", f"cli-{uuid.uuid4().hex[:8]}")
        provider = _create_provider(
            model_str,
            config=context.get("config"),
            token_store=context.get("_token_store"),
        )

        # GAP-05: Use shared factory for consistent wiring (hooks, skills, memory)
        agent_config = context.get("config")
        agent = create_agent(
            provider=provider,
            callbacks=callbacks,
            max_iterations=context.get("max_iterations", 100),
            max_cost_usd=context.get("max_budget", 10.0),
            mode=context.get("mode", "auto"),
            authority_mode=_current_authority_overlay(context.get("config")),
            model_name=model_str,
            workspace_dir=context.get("workspace_dir"),
            session_id=session_id,
            transcript_store=context.get("_transcript_store"),
            checkpoint_store=context.get("_checkpoint_store"),
            sandbox_config=getattr(agent_config, "sandbox", None),
        )
        context["_agent"] = agent
    elif hasattr(agent, "set_callbacks"):
        agent.set_callbacks(callbacks)

    # Show activity header
    console.print()
    _print_status_line(console, context)

    # Run agent
    try:
        result = await agent.run(user_input)
    except KeyboardInterrupt:
        console.print("\n  [warning]Interrupted[/]")
        return
    except Exception as e:
        console.print(f"\n  [error]Error: {e}[/]")
        return

    # Render LLM response as markdown
    console.print()
    if result:
        try:
            console.print(Markdown(result))
        except Exception:
            # Fallback to plain text if markdown rendering fails
            console.print(result)
    console.print()

    # Update context
    context["steps"] = context.get("steps", 0) + 1
    if hasattr(agent, "_budget"):
        summary = agent._budget.get_summary()
        context["cost"] = summary.get("total_cost_usd", 0)
        context["tool_calls"] = summary.get("iterations_used", 0)


def _import_tools() -> None:
    """Import all tool modules to trigger self-registration."""
    import importlib

    for module_name in [
        "ds_agent.tools.code_execution",
        "ds_agent.tools.data_loader",
        "ds_agent.tools.data_profiler",
        "ds_agent.tools.deployment",
        "ds_agent.tools.eda",
        "ds_agent.tools.evaluation",
        "ds_agent.tools.feature_eng",
        "ds_agent.tools.file_ops",
        "ds_agent.tools.memory_tools",
        "ds_agent.tools.modeling",
        "ds_agent.tools.reporting",
        "ds_agent.tools.schema_tools",
        "ds_agent.tools.skill_tools",
        "ds_agent.tools.sql_tools",
        "ds_agent.tools.user_interaction",
        "ds_agent.tools.web_search",
        "ds_agent.tools.portfolio_tools",
        "ds_agent.tools.learning_tools",
    ]:
        importlib.import_module(module_name)


def _create_provider(
    model: str,
    config: DSAgentConfig | None = None,
    token_store: AuthProfileStore | None = None,
) -> LLMProvider:
    """Create LLM provider using the shared runtime factory when config is available."""
    from ds_agent.providers.router import ProviderRouter

    try:
        if config is not None:
            shared_token_store = token_store or create_auth_profile_store(config)
            return create_provider_router(
                model,
                config,
                token_store=shared_token_store,
            )
        return ProviderRouter(model)
    except Exception:
        # 3.6 fix: No production code should use unittest.mock
        # Fallback: return a proper stub class instead of MagicMock
        return _NoApiKeyProvider(model)


class _NoApiKeyProvider:
    """Minimal stub provider returned when no API key is configured.

    Informs the user how to set up credentials instead of silently failing.
    Does not use unittest.mock — implements the LLMProvider interface directly.
    """

    def __init__(self, model: str) -> None:
        self._model = model

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        return LLMResponse(
            content=(
                "API key가 설정되지 않았습니다. "
                "`ds-agent init`으로 설정하거나 환경변수를 설정하세요.\n\n"
                "```bash\nexport ANTHROPIC_API_KEY=sk-ant-...\n"
                "# or\nexport OPENAI_API_KEY=sk-...\n```"
            ),
            usage=Usage(),
        )

    async def count_tokens(self, messages: list[ChatMessage]) -> int:
        return 0

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_id=self._model,
            provider="none",
            display_name=self._model,
            max_context_tokens=128_000,
            max_output_tokens=4096,
        )


def _current_authority_overlay(config: DSAgentConfig | None) -> str | None:
    if config is None:
        return None
    overlay = resolve_authority_overlay(
        getattr(config.gateway, "authority_overlay", None),
        getattr(config.gateway, "authority_overlay_started_at", None),
    )
    return None if overlay.mode is None else overlay.mode.value


def interactive_loop() -> None:
    """Main interactive REPL loop."""
    console = Console(theme=DS_THEME)
    config = load_config(get_default_config_path())
    token_store = create_auth_profile_store(config)
    transcript_store = JsonTranscriptStore(config.agent.workspace_dir)
    checkpoint_store = JsonCheckpointStore(config.agent.workspace_dir)

    context: dict = {
        "config": config,
        "model": config.provider.default_model,
        "mode": config.agent.mode,
        "max_iterations": config.agent.max_iterations,
        "max_budget": config.provider.max_budget_usd,
        "workspace_dir": config.agent.workspace_dir,
        "cost": 0.0,
        "steps": 0,
        "tool_calls": 0,
        "artifacts": [],
        "history": [],
        "_token_store": token_store,
        "_transcript_store": transcript_store,
        "_checkpoint_store": checkpoint_store,
        "should_exit": False,
    }

    _print_banner(console, context["model"], context["mode"])

    # 2.5 fix: Single event loop for the entire session — prevents async resource
    # invalidation that occurs when asyncio.run() creates a new loop each turn.
    # Save and restore the previous loop to avoid interfering with callers (tests).
    prev_loop: asyncio.AbstractEventLoop | None
    try:
        prev_loop = asyncio.get_event_loop()
        if prev_loop.is_closed():
            prev_loop = None
    except RuntimeError:
        prev_loop = None
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        while not context.get("should_exit"):
            try:
                user_input = console.input("[user.prompt]You>[/] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[muted]Goodbye.[/]")
                break

            if not user_input:
                continue

            # Slash commands
            if user_input.startswith("/"):
                handle_slash_command(user_input, console, context)
                continue

            # Agent turn
            context["history"].append({"role": "user", "content": user_input})
            loop.run_until_complete(_run_agent_turn(user_input, console, context))
    finally:
        loop.close()
        # Always restore — passing None clears the closed loop as current
        asyncio.set_event_loop(prev_loop)


def main() -> None:
    """Entry point for `ds-agent` command."""
    # Handle subcommands
    if len(sys.argv) > 1:
        subcmd = sys.argv[1]

        # ds-agent init → onboarding wizard
        if subcmd == "init":
            from ds_agent.cli.wizard.onboard import run_onboard

            run_onboard(Console(theme=DS_THEME))
            return

        # ds-agent version
        if subcmd in ("--version", "version"):
            print("ds-agent v0.1.0")
            return

        if subcmd == "contract":
            config = load_config(get_default_config_path())
            console = Console(theme=DS_THEME)
            run_contract_command(
                sys.argv[2:],
                console=console,
                workspace_dir=str(config.agent.workspace_dir),
            )
            return

        if subcmd == "integration":
            config = load_config(get_default_config_path())
            run_integration_command(
                sys.argv[2:],
                workspace_dir=str(config.agent.workspace_dir),
            )
            return

        if subcmd == "portfolio":
            config = load_config(get_default_config_path())
            console = Console(theme=DS_THEME)
            raise SystemExit(
                run_portfolio_command(
                    sys.argv[2:],
                    console=console,
                    workspace_dir=str(config.agent.workspace_dir),
                )
            )

        if subcmd == "learning":
            config = load_config(get_default_config_path())
            console = Console(theme=DS_THEME)
            raise SystemExit(
                run_learning_command(
                    sys.argv[2:],
                    console=console,
                    workspace_dir=str(config.agent.workspace_dir),
                )
            )

        if subcmd == "work":
            config = load_config(get_default_config_path())
            console = Console(theme=DS_THEME)
            raise SystemExit(
                run_work_command(
                    sys.argv[2:],
                    console=console,
                    workspace_dir=str(config.agent.workspace_dir),
                )
            )

        if subcmd == "delivery":
            config = load_config(get_default_config_path())
            console = Console(theme=DS_THEME)
            run_delivery_command(
                sys.argv[2:],
                console=console,
                workspace_dir=str(config.agent.workspace_dir),
                config=config,
            )
            return

        if subcmd == "mode":
            config_path = get_default_config_path()
            config = load_config(config_path)
            console = Console(theme=DS_THEME)
            raise SystemExit(
                run_mode_command(
                    sys.argv[2:],
                    console=console,
                    config_path=config_path,
                    config=config,
                )
            )

        if subcmd == "certification":
            config = load_config(get_default_config_path())
            console = Console(theme=DS_THEME)
            run_certification_command(
                sys.argv[2:],
                console=console,
                workspace_dir=str(config.agent.workspace_dir),
            )
            return

        if subcmd == "verdict":
            config = load_config(get_default_config_path())
            console = Console(theme=DS_THEME)
            raise SystemExit(
                run_verdict_command(
                    sys.argv[2:],
                    console=console,
                    workspace_dir=str(config.agent.workspace_dir),
                )
            )

        if subcmd == "semantic":
            config = load_config(get_default_config_path())
            console = Console(theme=DS_THEME)
            raise SystemExit(
                run_semantic_command(
                    sys.argv[2:],
                    console=console,
                    workspace_dir=str(config.agent.workspace_dir),
                    config=config,
                )
            )

        if subcmd == "eval":
            from ds_agent.evaluation.infrastructure.cli.eval_cli import run_eval_command

            config = load_config(get_default_config_path())
            console = Console(theme=DS_THEME)
            token_store = create_auth_profile_store(config)
            raise SystemExit(
                run_eval_command(
                    sys.argv[2:],
                    console=console,
                    workspace_dir=str(config.agent.workspace_dir),
                    provider_factory=lambda model: _create_provider(
                        model,
                        config=config,
                        token_store=token_store,
                    ),
                    default_model=config.provider.default_model,
                )
            )

        # ds-agent "message" → one-shot mode
        if not subcmd.startswith("-"):
            message = " ".join(sys.argv[1:])
            console = Console(theme=DS_THEME)
            config = load_config(get_default_config_path())
            token_store = create_auth_profile_store(config)
            transcript_store = JsonTranscriptStore(config.agent.workspace_dir)
            checkpoint_store = JsonCheckpointStore(config.agent.workspace_dir)
            context = {
                "config": config,
                "model": config.provider.default_model,
                "mode": config.agent.mode,
                "max_iterations": config.agent.max_iterations,
                "max_budget": config.provider.max_budget_usd,
                "workspace_dir": config.agent.workspace_dir,
                "cost": 0.0,
                "steps": 0,
                "tool_calls": 0,
                "artifacts": [],
                "history": [],
                "_token_store": token_store,
                "_transcript_store": transcript_store,
                "_checkpoint_store": checkpoint_store,
            }
            asyncio.run(_run_agent_turn(message, console, context))
            return

    # Default: Interactive mode
    interactive_loop()


if __name__ == "__main__":
    main()
