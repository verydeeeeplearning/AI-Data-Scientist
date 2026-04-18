"""Gemini CLI OAuth provider — subscription-backed via `gemini -p` subprocess.

Sibling of ``codex_oauth`` for the Gemini tier of the 3-way LLM connection
model (OAuth / LOCAL / API). Reads credentials from ``~/.gemini/oauth_creds.json``
(populated by ``gemini login``). The actual HTTPS call to Google's Code
Assist / GenerativeLanguage endpoints is handled entirely by the Gemini
CLI binary — this adapter only shells out and parses the JSON output.

Why subprocess instead of HTTP:
  The user's Gemini subscription authenticates against different endpoints
  than ``generativelanguage.googleapis.com`` (which expects API keys).
  The Gemini CLI encapsulates the exact auth flow including token refresh.
  Shelling out avoids duplicating that logic.

Limits (Phase 4 scope):
  - No tool calling — Gemini CLI's ``-p`` flag is one-shot text in/out.
    ``tools`` argument is accepted but ignored; callers get an LLMResponse
    with ``tool_calls=None``.
  - No streaming — CLI emits final JSON after generation.
  - System + user messages are concatenated with a simple separator;
    richer message-role semantics requires upgrading to the CLI's ACP mode
    (post-Phase 4 work).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import structlog

from ds_agent.domain.entities.messages import ChatMessage, LLMResponse, Role, Usage
from ds_agent.domain.entities.provider_models import ModelInfo

logger = structlog.get_logger()


def gemini_cli_available() -> bool:
    """Return True iff the `gemini` CLI binary is discoverable on PATH."""
    return shutil.which("gemini") is not None


def gemini_oauth_creds_path() -> Path:
    return Path(os.path.expanduser("~/.gemini/oauth_creds.json"))


def gemini_oauth_creds_present() -> bool:
    p = gemini_oauth_creds_path()
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return bool(data.get("access_token"))


# Default model used when ``model`` constructor arg is None.
DEFAULT_CLI_MODEL = "gemini-3-flash-preview"

_SCRATCH_CWD: str | None = None


def _default_scratch_cwd() -> str:
    """Return a cached empty tempdir to use as `gemini` CLI cwd.

    Running the CLI from the project dir or `~` triggers a heavy workspace
    context scan (readdir every subdir) that can hang or trip EPERM on
    `.tmp`/`.codex` artifacts on Windows. Running from an empty dir
    bypasses the scan entirely. We cache one dir per process so repeated
    calls do not pile up temp folders.
    """
    global _SCRATCH_CWD
    if _SCRATCH_CWD is None or not os.path.isdir(_SCRATCH_CWD):
        _SCRATCH_CWD = tempfile.mkdtemp(prefix="ds_agent_gemini_cli_")
    return _SCRATCH_CWD


def _messages_to_prompt(messages: list[ChatMessage]) -> str:
    """Flatten messages into a SINGLE-LINE prompt the CLI's ``-p`` flag
    accepts on Windows.

    The ``gemini.CMD`` wrapper re-parses its argv when invoked through
    ``cmd.exe`` and mishandles embedded newlines (ends up passing the
    post-newline text to an agentic interactive loop instead of to the
    generate call, which then hangs waiting for more input). We inline
    the role markers so the whole prompt is one physical argument.
    """
    parts: list[str] = []
    for m in messages:
        content = (m.content or "").replace("\n", " ").strip()
        if not content:
            continue
        if m.role == Role.SYSTEM:
            parts.append(f"System instructions: {content}")
        elif m.role == Role.USER:
            parts.append(f"User question: {content}")
        elif m.role == Role.ASSISTANT:
            parts.append(f"Prior assistant reply: {content}")
    return " ".join(parts).strip()


def _extract_usage(payload: dict, model: str) -> Usage:
    """Reconstruct a Usage object from the CLI's stats.models.<model>.tokens."""
    models = payload.get("stats", {}).get("models", {})
    # The CLI may use multiple internal models (utility_router, main).
    # Sum across all of them so callers see true cost.
    in_sum = 0
    out_sum = 0
    thought_sum = 0
    for _mdl, mdata in models.items():
        tok = mdata.get("tokens", {}) or {}
        in_sum += int(tok.get("input", 0) or 0)
        out_sum += int(tok.get("candidates", 0) or 0)
        thought_sum += int(tok.get("thoughts", 0) or 0)
    return Usage(
        input_tokens=in_sum,
        output_tokens=out_sum,
        reasoning_tokens=thought_sum,
    )


class GeminiCliProvider:
    """Gemini provider that delegates to the user's `gemini` CLI binary.

    Constructor mirrors the shape of GeminiOAuthProvider so ProviderRouter
    can swap in without callsite changes.
    """

    def __init__(
        self,
        model: str | None = None,
        *,
        cli_path: str | None = None,
        cwd: str | None = None,
        timeout: int = 180,
    ) -> None:
        self._model = model or DEFAULT_CLI_MODEL
        self._cli_path = cli_path or (shutil.which("gemini") or "gemini")
        # Running gemini from the project dir or `~` triggers a heavy workspace
        # context scan that can hang or EPERM on directories like .codex/.tmp.
        # Use an isolated empty tempdir by default (created once per process).
        self._cwd = (
            cwd
            or os.environ.get("DS_AGENT_GEMINI_CLI_CWD")
            or _default_scratch_cwd()
        )
        self._timeout = timeout

    @staticmethod
    def _build_clean_env() -> dict[str, str]:
        """Return an environment stripped of IDE companion hints.

        Keep only the minimum PATH / user-dir / system entries the CLI needs
        to locate Node.js, its config, and OAuth creds.
        """
        keep_prefixes = (
            "PATH",
            "PATHEXT",
            "USERPROFILE",
            "HOMEDRIVE",
            "HOMEPATH",
            "APPDATA",
            "LOCALAPPDATA",
            "SYSTEMROOT",
            "SYSTEMDRIVE",
            "PROGRAMFILES",
            "PROGRAMDATA",
            "TEMP",
            "TMP",
            "COMSPEC",
            "OS",
            "PROCESSOR",
            "NUMBER_OF_PROCESSORS",
            "WINDIR",
        )
        drop_prefixes = (
            "VSCODE_",
            "GEMINI_CLI_IDE",
            "TERM_PROGRAM",
            "CURSOR_",
            "ANTIGRAVITY_",
        )

        env: dict[str, str] = {}
        for k, v in os.environ.items():
            k_upper = k.upper()
            if any(k_upper.startswith(p) for p in drop_prefixes):
                continue
            if any(k_upper.startswith(p) for p in keep_prefixes) or k_upper in {
                "PATH", "PATHEXT", "COMSPEC", "OS"
            }:
                env[k] = v
        return env

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        on_delta: object = None,
        **kwargs: object,
    ) -> LLMResponse:
        """Call `gemini -p PROMPT -o json` and parse the response.

        ``tools`` / ``temperature`` / ``max_tokens`` / ``on_delta`` are
        accepted for interface compat but ignored by this adapter. Phase 4
        scope is limited to text-in/text-out parity.
        """
        if tools:
            logger.debug(
                "gemini_cli_tools_ignored",
                msg="GeminiCliProvider does not support tool calls; `tools` dropped",
                tool_count=len(tools),
            )
        prompt = _messages_to_prompt(messages)
        # On Windows the `gemini` entry is a .CMD shim whose argparse behavior
        # drifts depending on how the subprocess is launched. Routing through
        # cmd.exe /c stabilizes argument forwarding and, empirically, is the
        # only way the CLI produces JSON output (direct invocation falls back
        # to an "I'm ready to help" agentic opener). On POSIX we call the
        # binary directly.
        base_cmd = [self._cli_path, "-p", prompt, "-o", "json", "-m", self._model]
        cmd = ["cmd.exe", "/c", *base_cmd] if os.name == "nt" else base_cmd

        # IDE companion integration (VS Code / Cursor / Antigravity) forcibly
        # pins the CLI's workspace path to the IDE's open folder and triggers
        # a heavy directory scan. When that scan hits EPERM (common on pytest
        # tmp dirs) the subprocess hangs for the full timeout. We aggressively
        # scrub every env var that signals "running inside an IDE" so the CLI
        # falls back to pure headless mode and honors our chosen cwd.
        env = self._build_clean_env()

        proc = await asyncio.to_thread(
            subprocess.run,
            cmd,
            input=b"",
            capture_output=True,
            timeout=self._timeout,
            cwd=self._cwd,
            env=env,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"gemini CLI failed (rc={proc.returncode}): {stderr}")

        stdout = proc.stdout.decode("utf-8", errors="replace").strip()
        # The CLI may print warnings to stdout before the JSON payload.
        # Locate the first '{' and parse from there.
        brace = stdout.find("{")
        if brace < 0:
            raise RuntimeError(
                f"gemini CLI: no JSON found in stdout (first 300 chars): {stdout[:300]}"
            )
        try:
            payload = json.loads(stdout[brace:])
        except json.JSONDecodeError as exc:
            head = stdout[brace:brace + 200]
            raise RuntimeError(
                f"gemini CLI: JSON parse failed: {exc}; head={head}"
            ) from exc

        response_text = payload.get("response") or ""
        usage = _extract_usage(payload, self._model)

        return LLMResponse(
            content=response_text,
            tool_calls=None,
            usage=usage,
            model=self._model,
            stop_reason="stop",
        )

    async def count_tokens(self, messages: list[ChatMessage]) -> int:
        # Cheap heuristic (char-based). The CLI does not expose a tokenize
        # subcommand, so exact counting would require extra API calls.
        return sum(len(m.content or "") for m in messages) // 4

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_id=self._model,
            provider="google-gemini-cli",
            display_name=f"{self._model} (CLI OAuth)",
            max_context_tokens=1_048_576,
            max_output_tokens=65_536,
            supports_tools=False,  # Honest: CLI `-p` path doesn't expose tool_calls
            supports_vision=False,  # Same — image input would need ACP mode
        )
