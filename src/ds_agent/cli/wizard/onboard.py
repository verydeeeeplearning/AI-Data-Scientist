"""Interactive onboarding wizard — ds-agent init.

Supports three auth tiers:
1. OAuth login (Codex, Gemini) — no API key needed
2. Free API key (Groq, Mistral, OpenRouter) — no credit card
3. Paid API key (Anthropic, OpenAI) — billing required
"""

from __future__ import annotations

import os
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from ds_agent.config.loader import get_default_config_path, save_config
from ds_agent.config.schema import DSAgentConfig, OAuthConfig, ProviderConfig
from ds_agent.infrastructure.secrets.api_key_manager import create_api_key_manager
from ds_agent.infrastructure.secrets.config_secret_manager import create_config_secret_manager

# Provider definitions: (display_name, provider_id, model_string, auth_type, env_var)
OAUTH_PROVIDERS = [
    ("ChatGPT 계정 로그인 (Codex)", "codex", "codex/gpt-5.4", "oauth", None),
    ("Google 계정 로그인 (Gemini)", "gemini", "gemini/gemini-2.5-pro", "oauth", None),
]

_OR_FREE_MODEL = "openrouter/google/gemini-2.5-pro-exp-03-25:free"

FREE_API_PROVIDERS = [
    ("Groq (무료, Llama 3)", "groq", "groq/llama-3.3-70b", "api_key", "GROQ_API_KEY"),
    ("Mistral (무료)", "mistral", "mistral/mistral-small-latest", "api_key", "MISTRAL_API_KEY"),
    ("OpenRouter (무료 모델)", "openrouter", _OR_FREE_MODEL, "api_key", "OPENROUTER_API_KEY"),
]

PAID_API_PROVIDERS = [
    (
        "Anthropic (Claude)",
        "anthropic",
        "anthropic/claude-sonnet-4",
        "api_key",
        "ANTHROPIC_API_KEY",
    ),
    ("OpenAI (GPT)", "openai", "openai/gpt-4.1", "api_key", "OPENAI_API_KEY"),
]

LOCAL_PROVIDERS = [
    ("Ollama (로컬)", "ollama", "ollama/qwen2.5:32b", "local", None),
]


def run_onboard(console: Console | None = None) -> None:
    """Run the interactive onboarding wizard."""
    console = console or Console()

    console.print(
        Panel(
            "[bold cyan]DS Agent Setup[/]\nAI Data Scientist 에이전트 초기 설정",
            border_style="cyan",
        )
    )

    # Auto-detect existing credentials
    detected = _detect_existing_auth()
    if detected:
        name, model = detected
        console.print(f"\n[green]✓ {name} 감지됨[/]")
        if _ask_yn(console, "이 프로바이더를 사용할까요?", default=True):
            _save_and_finish(console, model)
            return

    # Show provider options by tier
    console.print("\n[bold]LLM 프로바이더 선택:[/]")

    console.print("\n  [bold green]🔑 로그인 (API key 불필요)[/]")
    for i, (name, *_) in enumerate(OAUTH_PROVIDERS, 1):
        console.print(f"    {i}. {name}")

    console.print("\n  [bold yellow]🆓 무료 API key (신용카드 불필요)[/]")
    offset = len(OAUTH_PROVIDERS)
    for i, (name, *_) in enumerate(FREE_API_PROVIDERS, offset + 1):
        console.print(f"    {i}. {name}")

    console.print("\n  [bold blue]💳 유료 API key[/]")
    offset2 = offset + len(FREE_API_PROVIDERS)
    for i, (name, *_) in enumerate(PAID_API_PROVIDERS, offset2 + 1):
        console.print(f"    {i}. {name}")

    console.print("\n  [bold dim]🖥 로컬[/]")
    offset3 = offset2 + len(PAID_API_PROVIDERS)
    for i, (name, *_) in enumerate(LOCAL_PROVIDERS, offset3 + 1):
        console.print(f"    {i}. {name}")

    all_providers = OAUTH_PROVIDERS + FREE_API_PROVIDERS + PAID_API_PROVIDERS + LOCAL_PROVIDERS
    total = len(all_providers)
    choice = console.input(f"\n  선택 (1-{total}, default=1): ").strip() or "1"
    idx = int(choice) - 1 if choice.isdigit() and 1 <= int(choice) <= total else 0
    name, provider_id, model, auth_type, env_var = all_providers[idx]

    # Handle auth by type
    if auth_type == "oauth":
        _handle_oauth_login(console, provider_id, model)
    elif auth_type == "api_key":
        _handle_api_key(console, provider_id, model, env_var)
    elif auth_type == "local":
        console.print("\n[dim]Ollama가 설치되어 있어야 합니다: https://ollama.ai[/]")
        _save_and_finish(console, model)


def _detect_existing_auth() -> tuple[str, str] | None:
    """Detect existing credentials in order of preference."""
    # 1. Codex CLI auth
    codex_auth = Path.home() / ".codex" / "auth.json"
    if codex_auth.exists():
        try:
            import json

            data = json.loads(codex_auth.read_text())
            if data.get("auth_mode") == "chatgpt":
                return "ChatGPT (Codex CLI)", "codex/gpt-5.4"
        except Exception:
            pass

    # 2. API keys from environment
    env_checks = [
        ("ANTHROPIC_API_KEY", "Anthropic", "anthropic/claude-sonnet-4"),
        ("OPENAI_API_KEY", "OpenAI", "openai/gpt-4.1"),
        ("GEMINI_API_KEY", "Google Gemini", "gemini/gemini-2.5-pro"),
        ("GROQ_API_KEY", "Groq", "groq/llama-3.3-70b"),
        ("MISTRAL_API_KEY", "Mistral", "mistral/mistral-small-latest"),
        ("OPENROUTER_API_KEY", "OpenRouter", "openrouter/google/gemini-2.5-pro-exp-03-25:free"),
    ]
    for env_var, name, model in env_checks:
        if os.environ.get(env_var):
            return f"{name} ({env_var})", model

    return None


def _handle_oauth_login(console: Console, provider_id: str, model: str) -> None:
    """Handle OAuth-based login."""
    import asyncio

    from ds_agent.infrastructure.auth.oauth_service import OAuthService
    from ds_agent.infrastructure.auth.token_store import AuthProfileStore

    store = AuthProfileStore()

    if provider_id == "codex":
        codex_auth = Path.home() / ".codex" / "auth.json"
        if codex_auth.exists():
            console.print("\n[green]✓ Codex CLI 인증 정보 감지됨[/]")
            _save_and_finish(console, model)
            return

        console.print("\n[yellow]Codex CLI 로그인을 시작합니다...[/]")
        service = OAuthService(store=store)
        try:
            tokens = asyncio.get_event_loop().run_until_complete(service.start_codex_login())
            console.print("[green]✓ Codex 인증 완료[/]")
            _save_and_finish(console, model)
        except RuntimeError as e:
            console.print(f"\n[yellow]{e}[/]")
        return

    if provider_id == "gemini":
        # Offer two options: OAuth or API key
        console.print(
            "\n[bold]Google Gemini 인증 방법:[/]\n"
            "  [cyan]1[/]. OAuth 로그인 (Google 계정, 유료 quota 사용)\n"
            "  [cyan]2[/]. API Key (AI Studio 무료 키)"
        )
        choice = console.input("\n  선택 (1/2): ").strip()

        if choice == "1":
            client_id = console.input("  Google OAuth Client ID: ").strip()
            client_secret = console.input("  Google OAuth Client Secret (없으면 Enter): ").strip()
            if not client_id:
                console.print("[red]Client ID가 필요합니다.[/]")
                return

            service = OAuthService(
                store=store,
                gemini_client_id=client_id,
                gemini_client_secret=client_secret,
            )
            console.print("\n[cyan]브라우저에서 Google 로그인이 열립니다...[/]")
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(service.start_gemini_login())
                console.print("[dim]인증 완료 대기 중...[/]")
                tokens = loop.run_until_complete(service.wait_for_login("gemini"))
                console.print(f"[green]✓ Gemini OAuth 완료[/] ({tokens.email or 'authenticated'})")
                if client_secret:
                    create_config_secret_manager().set(
                        "oauth.gemini_client_secret",
                        client_secret,
                    )
                # Save OAuth config
                config = DSAgentConfig(
                    provider=ProviderConfig(default_model=model),
                    oauth=OAuthConfig(
                        gemini_client_id=client_id,
                        gemini_client_secret=client_secret,
                    ),
                )
                config_path = get_default_config_path()
                save_config(config, config_path)
                _finish_message(console, model, config_path)
                loop.close()
            except Exception as e:
                console.print(f"[red]OAuth 실패: {e}[/]")
            return

        # Option 2: API key (existing flow)
        console.print(
            "\n[bold]Google Gemini API Key 설정:[/]\n"
            "  1. [cyan]https://aistudio.google.com[/] 접속\n"
            "  2. API key 생성 (무료, 신용카드 불필요)\n"
            "  3. 아래에 입력"
        )
        api_key = console.input("\n  Gemini API Key: ").strip()
        if api_key:
            create_api_key_manager().set("gemini", api_key)
            config = DSAgentConfig(
                provider=ProviderConfig(default_model=model),
            )
            config_path = get_default_config_path()
            save_config(config, config_path)
            console.print("\n[dim]팁: 환경변수로도 설정 가능: export GEMINI_API_KEY=<your-key>[/]")
            _finish_message(console, model, config_path)
        return


def _handle_api_key(console: Console, provider_id: str, model: str, env_var: str | None) -> None:
    """Handle API key input."""
    if env_var and os.environ.get(env_var):
        console.print(f"\n[green]✓ {env_var} 환경변수 감지됨[/]")
        _save_and_finish(console, model)
        return

    if env_var:
        console.print(f"\n  {env_var}를 입력하세요.")
        if provider_id in ("groq", "mistral", "openrouter"):
            urls = {
                "groq": "https://console.groq.com",
                "mistral": "https://console.mistral.ai",
                "openrouter": "https://openrouter.ai/keys",
            }
            console.print(f"  [dim]발급: {urls.get(provider_id, '')} (무료)[/]")

        api_key = console.input(f"\n  {env_var}: ").strip()
        if api_key:
            # SEC-09 fix: Never print key material to terminal
            console.print(f"[dim]팁: 환경변수로도 설정 가능: export {env_var}=<your-key>[/]")
            # BUG-2.3 fix: Actually persist the API key to config
            create_api_key_manager().set(provider_id, api_key)
            config = DSAgentConfig(provider=ProviderConfig(default_model=model))
            config_path = get_default_config_path()
            save_config(config, config_path)
            _finish_message(console, model, config_path)
            return

    _save_and_finish(console, model)


def _save_and_finish(console: Console, model: str) -> None:
    config = DSAgentConfig(provider=ProviderConfig(default_model=model))
    config_path = get_default_config_path()
    save_config(config, config_path)
    _finish_message(console, model, config_path)


def _finish_message(console: Console, model: str, config_path: Path) -> None:
    console.print()
    console.print(
        Panel(
            f"[bold green]✓ 설정 완료![/]\n\n"
            f"  설정 파일: {config_path}\n"
            f"  기본 모델: {model}\n\n"
            f"[bold]시작하기:[/]\n"
            f"  [cyan]ds-agent[/]                    → 대화형 모드\n"
            f'  [cyan]ds-agent "데이터 분석해줘"[/]   → 바로 실행',
            title="DS Agent",
            border_style="green",
        )
    )


def _ask_yn(console: Console, question: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = console.input(f"  {question} [{hint}]: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes", "ㅇ", "네")
