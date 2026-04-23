"""Record Gemini CLI OAuth subprocess fixture for 3-way parity (Phase 4).

Mirrors ``record_codex_fixture.py``. Delegates every `gemini -p` call
through the real CLI (consuming the user's Gemini subscription), captures
the JSON stdout, sanitizes OAuth creds (access/id/refresh tokens + project
IDs + session_id + email hints), and writes a JSON fixture per scenario.

Scenarios intentionally match the Codex fixture so Phase 6 can eventually
compare provider-to-provider parity on a shared prompt set.

Cost: consumes ~3 Gemini CLI conversation turns (tiny prompts). The CLI
issues two internal model calls per prompt (utility_router + main), so
the stats block is summed across models.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.providers.gemini_cli import (
    GeminiCliProvider,
    gemini_cli_available,
    gemini_oauth_creds_path,
    gemini_oauth_creds_present,
)

FIXTURE_DIR = _ROOT / "tests" / "fixtures" / "llm_cassettes" / "gemini_cli"


@dataclass
class Scenario:
    sid: str
    system: str
    user: str


SCENARIOS: list[Scenario] = [
    Scenario(
        sid="gemini-P01",
        system="You are a concise assistant. Answer in one short sentence.",
        user="What is the capital of France?",
    ),
    Scenario(
        sid="gemini-P02",
        system="Respond only with a single JSON object {\"x\": N}.",
        user="Return x=42.",
    ),
    Scenario(
        sid="gemini-P03",
        system="You are a data science tutor.",
        user="In one sentence, what is overfitting?",
    ),
]


def _load_oauth_secrets() -> dict[str, str]:
    """Read ~/.gemini/oauth_creds.json and collect every value worth redacting."""
    path = gemini_oauth_creds_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        "GEMINI_ACCESS_TOKEN": str(data.get("access_token") or ""),
        "GEMINI_REFRESH_TOKEN": str(data.get("refresh_token") or ""),
        "GEMINI_ID_TOKEN": str(data.get("id_token") or ""),
    }


def _load_account_secrets() -> dict[str, str]:
    """Extract email + project hints from google_accounts.json if present."""
    path = Path(os.path.expanduser("~/.gemini/google_accounts.json"))
    if not path.exists():
        return {}
    secrets: dict[str, str] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return secrets
    # File shape varies across gemini CLI versions; keep it defensive.
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, str) and (
                "@" in v or k.lower() in {"project_id", "projectid"}
            ):
                secrets[f"GEMINI_ACCOUNT_{k.upper()}"] = v
    return secrets


def _sanitize(text: str, secrets: dict[str, str]) -> str:
    for placeholder, value in sorted(
        secrets.items(), key=lambda kv: -len(kv[1])
    ):
        if value:
            text = text.replace(value, f"<{placeholder}>")
    # JWT-shaped fallback (id_token is always JWT)
    jwt_re = r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"
    text = re.sub(jwt_re, "<REDACTED_JWT>", text)
    # Email fallback (broad but safe)
    text = re.sub(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        "<REDACTED_EMAIL>",
        text,
    )
    return text


class _Capturer:
    """Wraps subprocess.run so we can snapshot the exact bytes it returns."""

    def __init__(self):
        self.captures: list[dict] = []
        self._original = subprocess.run

    def _wrapped(self, *args, **kwargs):
        result = self._original(*args, **kwargs)
        cmd = args[0] if args else kwargs.get("args")
        # Match any argv containing a `gemini*` token — covers direct
        # invocation on POSIX and `cmd.exe /c gemini ...` on Windows.
        if isinstance(cmd, list) and any(
            isinstance(a, str) and "gemini" in os.path.basename(str(a)).lower()
            for a in cmd
        ):
            self.captures.append({
                "cmd": cmd,
                "returncode": result.returncode,
                "stdout": bytes(result.stdout or b""),
                "stderr": bytes(result.stderr or b""),
            })
        return result

    def install(self):
        subprocess.run = self._wrapped  # type: ignore[assignment]

    def uninstall(self):
        subprocess.run = self._original  # type: ignore[assignment]


async def _record_one(
    provider: GeminiCliProvider,
    scenario: Scenario,
    secrets: dict[str, str],
) -> dict:
    capturer = _Capturer()
    capturer.install()
    try:
        response = await provider.chat(
            messages=[
                ChatMessage(role=Role.SYSTEM, content=scenario.system),
                ChatMessage(role=Role.USER, content=scenario.user),
            ],
            temperature=0.0,
        )
    finally:
        capturer.uninstall()

    if not capturer.captures:
        raise RuntimeError(f"{scenario.sid}: no gemini subprocess call captured")
    capture = capturer.captures[-1]
    usage = response.usage
    usage_dict = {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_tokens": usage.reasoning_tokens,
    }
    return {
        "scenario_id": scenario.sid,
        "prompt_system": scenario.system,
        "prompt_user": scenario.user,
        "response_text": response.content or "",
        "response_model": response.model,
        "usage": usage_dict,
        "capture": capture,
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--scenario", default=None)
    args = parser.parse_args()

    if not gemini_cli_available():
        print("ERROR: gemini CLI not on PATH", file=sys.stderr)
        return 1
    if not gemini_oauth_creds_present():
        print("ERROR: ~/.gemini/oauth_creds.json missing", file=sys.stderr)
        return 1

    secrets = {**_load_oauth_secrets(), **_load_account_secrets()}

    if args.dry_run:
        print(
            f"dry-run OK: gemini CLI present, oauth creds present, "
            f"{sum(1 for v in secrets.values() if v)} secrets loaded"
        )
        return 0

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    provider = GeminiCliProvider()

    scenarios = [s for s in SCENARIOS if not args.scenario or s.sid == args.scenario]

    manifest_entries: list[dict] = []
    for scenario in scenarios:
        print(f"[record] {scenario.sid} -- calling gemini CLI...")
        try:
            result = await _record_one(provider, scenario, secrets)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            print(f"[FAIL] {scenario.sid}: {err}", file=sys.stderr)
            manifest_entries.append({
                "scenario_id": scenario.sid,
                "recorded": False,
                "error": err[:300],
            })
            continue

        cap = result["capture"]
        sanitized_stdout = _sanitize(
            cap["stdout"].decode("utf-8", errors="replace"),
            secrets,
        )
        sanitized_stderr = _sanitize(
            cap["stderr"].decode("utf-8", errors="replace"),
            secrets,
        )
        # Redact prompt arg from cmd (contains the user prompt verbatim,
        # which is already stored in prompt_user — keep cmd structure for
        # debug but shorten the prompt so the fixture stays readable).
        sanitized_cmd = []
        skip_next = False
        for arg in cap["cmd"]:
            if skip_next:
                sanitized_cmd.append("<PROMPT>")
                skip_next = False
                continue
            if arg == "-p":
                sanitized_cmd.append(arg)
                skip_next = True
                continue
            if isinstance(arg, str):
                sanitized_cmd.append(_sanitize(arg, secrets))
            else:
                sanitized_cmd.append(arg)

        fixture = {
            "scenario_id": result["scenario_id"],
            "recorded_with_model": result["response_model"],
            "prompt_system": result["prompt_system"],
            "prompt_user": result["prompt_user"],
            "response_preview": (result["response_text"] or "")[:200],
            "response_model": result["response_model"],
            "usage": result["usage"],
            "subprocess": {
                "cmd": sanitized_cmd,
                "returncode": cap["returncode"],
                "stdout": sanitized_stdout,
                "stderr": sanitized_stderr,
            },
        }
        fixture_path = FIXTURE_DIR / f"{scenario.sid}.json"
        fixture_path.write_text(
            json.dumps(fixture, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        h = hashlib.sha256((result["response_text"] or "").encode("utf-8")).hexdigest()
        manifest_entries.append({
            "scenario_id": scenario.sid,
            "fixture": str(fixture_path.relative_to(_ROOT)).replace(os.sep, "/"),
            "recorded": True,
            "response_sha256": h,
            "usage": result["usage"],
        })
        print(f"[ok] {scenario.sid}: response_sha256={h[:16]}...")

    manifest = {
        "provider": "gemini_cli_oauth",
        "transport": "subprocess",
        "entries": manifest_entries,
    }
    (FIXTURE_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[done] wrote {len(manifest_entries)} fixtures + manifest to {FIXTURE_DIR}")
    return 0 if all(e.get("recorded") for e in manifest_entries) else 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
