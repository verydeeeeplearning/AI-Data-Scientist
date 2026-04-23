"""OpenAI Codex OAuth provider — use ChatGPT account login.

Reads credentials from ~/.codex/auth.json (Codex CLI)
or triggers OAuth PKCE flow for browser-based login.
Usage is included with ChatGPT Plus/Pro subscription.

Uses curl subprocess to call chatgpt.com/backend-api because
Python HTTP clients get blocked by Cloudflare (TLS fingerprint).
curl passes Cloudflare's bot detection.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import subprocess
from pathlib import Path

import structlog

from ds_agent.domain.entities.messages import (
    ChatMessage,
    LLMResponse,
    Role,
)
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.providers.base import (
    messages_to_responses_input,
    openai_tools_to_responses_format,
    responses_response_to_llm_response,
)

logger = structlog.get_logger()

CODEX_MODELS: dict[str, dict] = {
    # GPT-5.4 via ChatGPT Pro (general purpose, confirmed working)
    "gpt-5.4": {
        "display_name": "GPT-5.4",
        "max_context": 1_050_000,
        "max_output": 128_000,
    },
    # Codex-specific models (code-tuned variants, confirmed working)
    "gpt-5.3-codex": {
        "display_name": "GPT-5.3 Codex",
        "max_context": 400_000,
        "max_output": 128_000,
    },
    "gpt-5.3-codex-spark": {
        "display_name": "GPT-5.3 Codex Spark",
        "max_context": 128_000,
        "max_output": 128_000,
    },
    "gpt-5.2-codex": {
        "display_name": "GPT-5.2 Codex",
        "max_context": 400_000,
        "max_output": 128_000,
    },
    "gpt-5.1-codex": {
        "display_name": "GPT-5.1 Codex",
        "max_context": 272_000,
        "max_output": 128_000,
    },
    "gpt-5.1-codex-mini": {
        "display_name": "GPT-5.1 Codex Mini",
        "max_context": 272_000,
        "max_output": 128_000,
    },
}


def read_codex_credentials(
    codex_home: str | None = None,
) -> dict | None:
    """Read OAuth credentials from Codex CLI's auth.json.

    Returns dict with access_token, refresh_token, account_id or None.
    """
    if codex_home is None:
        codex_home = str(Path.home() / ".codex")

    auth_path = Path(codex_home) / "auth.json"
    if not auth_path.exists():
        return None

    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    # Only support chatgpt OAuth mode
    if data.get("auth_mode") != "chatgpt":
        return None

    tokens = data.get("tokens", {})
    access_token = tokens.get("access_token")
    if not access_token:
        return None

    return {
        "access_token": access_token,
        "refresh_token": tokens.get("refresh_token"),
        "account_id": tokens.get("account_id"),
    }


class CodexOAuthProvider:
    """OpenAI provider using ChatGPT OAuth credentials.

    Uses the same credentials as Codex CLI — either reads from
    ~/.codex/auth.json or triggers browser-based OAuth login.
    No API key or billing setup required.

    Token resolution priority:
    1. Explicit ``access_token`` parameter
    2. ``~/.codex/auth.json`` (Codex CLI)
    3. ``token_store`` (DS Agent auth profiles)
    """

    def __init__(
        self,
        model: str = "gpt-5.4",
        access_token: str | None = None,
        codex_home: str | None = None,
        token_store: object | None = None,
    ) -> None:
        self._model = model
        self._token_store = token_store
        self._account_id: str = ""

        if access_token:
            self._access_token = access_token
        else:
            # Try Codex CLI file first
            creds = read_codex_credentials(codex_home)
            if creds:
                self._access_token = creds["access_token"]
            elif token_store is not None:
                # Try auth profile store
                load_by_provider = getattr(token_store, "load_by_provider", None)
                profile = load_by_provider("codex") if callable(load_by_provider) else None
                oauth = getattr(profile, "oauth", None) if profile is not None else None
                access_token_from_store = (
                    getattr(oauth, "access", None) if oauth is not None else None
                )
                if isinstance(access_token_from_store, str) and access_token_from_store:
                    self._access_token = access_token_from_store
                else:
                    raise RuntimeError(
                        "Codex CLI credentials not found. "
                        "Run 'codex login' first, or use ds-agent init."
                    )
            else:
                raise RuntimeError(
                    "Codex CLI credentials not found. "
                    "Run 'codex login' first, or use ds-agent init."
                )

        # Read account_id for ChatGPT-Account-Id header (if not already set)
        if not self._account_id:
            creds = read_codex_credentials(codex_home)
            self._account_id = (creds or {}).get("account_id", "")

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        on_delta: object = None,
        **kwargs: object,
    ) -> LLMResponse:
        """Call ChatGPT backend API via curl (bypasses Cloudflare TLS fingerprinting).

        Uses ``POST https://chatgpt.com/backend-api/wham/responses`` with SSE streaming.
        """
        # System messages are pulled out into `instructions`; the shared
        # `messages_to_responses_input` helper emits the non-system items
        # (message / function_call / function_call_output) in the exact
        # format the Responses API expects.
        system_text = "\n".join(
            (m.content or "") for m in messages if m.role == Role.SYSTEM
        ).strip()
        non_system = [m for m in messages if m.role != Role.SYSTEM]
        input_items = messages_to_responses_input(non_system)

        body: dict = {
            "model": self._model,
            "instructions": system_text or "You are a helpful assistant.",
            "input": input_items,
            "stream": True,
            "store": False,
        }
        if tools:
            body["tools"] = openai_tools_to_responses_format(tools)
            body["tool_choice"] = "auto"
        # NOTE: chatgpt.com/backend-api/wham/responses does not support
        # max_output_tokens; honor budget via agent-level limits instead.

        events = await self._curl_sse(
            "https://chatgpt.com/backend-api/wham/responses",
            body,
        )
        return self._parse_sse_events(events)

    async def _curl_sse(self, url: str, body: dict) -> list[dict]:
        """POST via curl with SSE streaming, returns list of parsed events.

        Body is passed via stdin (``--data-binary @-``) to avoid Windows'
        8191-char command-line length limit on large agent prompts.
        """
        body_bytes = json.dumps(body).encode("utf-8")
        cmd = [
            "curl", "-s", "-N", "-X", "POST", url,
            "-H", f"Authorization: Bearer {self._access_token}",
            "-H", "Content-Type: application/json",
            "-H", "Accept: text/event-stream",
            "-H", "User-Agent: CodexBar",
            "-H", f"ChatGPT-Account-Id: {self._account_id}",
            "--data-binary", "@-",
        ]
        proc = await asyncio.to_thread(
            subprocess.run,
            cmd,
            input=body_bytes,
            capture_output=True,
            timeout=300,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace")[:200]
            raise RuntimeError(f"curl failed (rc={proc.returncode}): {stderr}")

        output = proc.stdout.decode("utf-8", errors="replace").strip()

        # Not SSE? Probably an error JSON
        if not output.startswith("event:") and not output.startswith("data:"):
            if "<html>" in output[:100].lower():
                raise RuntimeError("Cloudflare blocked the request")
            try:
                err_data = json.loads(output)
                detail = err_data.get("detail") or err_data.get("error") or output[:300]
                raise RuntimeError(f"API error: {detail}")
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Unexpected response: {output[:300]}") from exc

        # Parse SSE events
        events: list[dict] = []
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str and data_str != "[DONE]":
                    with contextlib.suppress(json.JSONDecodeError):
                        events.append(json.loads(data_str))
        return events

    @staticmethod
    def _parse_sse_events(events: list[dict]) -> LLMResponse:
        """Assemble LLMResponse from SSE events.

        The chatgpt.com/backend-api/wham/responses endpoint delivers assistant
        text as a series of ``response.output_text.delta`` events and emits
        ``response.output_item.done`` for function calls. The final
        ``response.completed`` event contains usage/model metadata but leaves
        the ``output`` array empty, so we synthesize a final response dict
        from the accumulated events and delegate to the shared parser.
        """
        text_parts: list[str] = []
        completed_output: list[dict] = []
        final_response: dict = {}

        for ev in events:
            ev_type = ev.get("type", "")

            if ev_type == "response.output_text.delta":
                delta = ev.get("delta", "")
                if isinstance(delta, str):
                    text_parts.append(delta)

            elif ev_type == "response.output_item.done":
                item = ev.get("item")
                if isinstance(item, dict):
                    completed_output.append(item)

            elif ev_type == "response.completed":
                final_response = ev.get("response") or {}

        # Ensure there's at least one assistant message item carrying the
        # streamed text (the backend leaves the output array empty on the
        # completed event).
        assembled_text = "".join(text_parts)
        has_message_item = any(
            item.get("type") == "message" for item in completed_output
        )
        if assembled_text and not has_message_item:
            completed_output.insert(0, {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": assembled_text}],
            })

        # Overlay the assembled output on top of whatever the completed event
        # shipped, preserving its usage/model/status fields.
        final_response = {**final_response, "output": completed_output}
        return responses_response_to_llm_response(final_response)

    async def count_tokens(self, messages: list[ChatMessage]) -> int:
        return sum(len(m.content or "") for m in messages) // 4

    def get_model_info(self) -> ModelInfo:
        meta = CODEX_MODELS.get(self._model, {})
        return ModelInfo(
            model_id=self._model,
            provider="openai-codex",
            display_name=meta.get("display_name", self._model),
            max_context_tokens=meta.get("max_context", 128_000),
            max_output_tokens=meta.get("max_output", 4_096),
            supports_tools=True,
        )
