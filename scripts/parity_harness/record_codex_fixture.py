"""Record Codex OAuth subprocess fixture for 3-way parity (S22).

Usage:
    uv run python scripts/parity_harness/record_codex_fixture.py

Reads credentials from ~/.codex/auth.json (CodexOAuthProvider default).
Runs 3 scenarios, captures subprocess.run stdout bytes, sanitizes secrets,
writes fixture JSON under tests/fixtures/llm_cassettes/codex/.

Cost: consumes ~3 ChatGPT Plus conversation turns (tiny prompts).
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

# Add repo src/ so imports work without install
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.providers.codex_oauth import (
    CodexOAuthProvider,
    read_codex_credentials,
)

FIXTURE_DIR = _ROOT / "tests" / "fixtures" / "llm_cassettes" / "codex"
MODEL = "gpt-5.4"


@dataclass
class Scenario:
    """One Codex fixture scenario -- kept small to save Plus quota."""

    sid: str
    system: str
    user: str


SCENARIOS: list[Scenario] = [
    Scenario(
        sid="codex-P01",
        system="You are a concise assistant. Answer in one short sentence.",
        user="What is the capital of France?",
    ),
    Scenario(
        sid="codex-P02",
        system="Respond only with a single JSON object {\"x\": N}.",
        user="Return x=42.",
    ),
    Scenario(
        sid="codex-P03",
        system="You are a data science tutor.",
        user="In one sentence, what is overfitting?",
    ),
]


def _sanitize(blob: bytes, secrets: dict[str, str]) -> bytes:
    """Replace every occurrence of every secret with a placeholder.

    `secrets` maps placeholder name -> actual value. Longer secrets are
    substituted first to avoid prefix collisions.
    """
    text = blob.decode("utf-8", errors="replace")
    for placeholder, value in sorted(
        secrets.items(), key=lambda kv: -len(kv[1])
    ):
        if value:
            text = text.replace(value, f"<{placeholder}>")
    # Belt-and-suspenders: any eyJ... JWT-looking string we missed
    jwt_re = r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"
    text = re.sub(jwt_re, "<REDACTED_JWT>", text)
    return text.encode("utf-8")


class _Capturer:
    """Wraps subprocess.run so we can snapshot the exact bytes it returns."""

    def __init__(self):
        self.captures: list[dict] = []
        self._original = subprocess.run

    def _wrapped(self, *args, **kwargs):
        result = self._original(*args, **kwargs)
        cmd = args[0] if args else kwargs.get("args")
        # Only capture the chatgpt.com call, not other curl noise
        if isinstance(cmd, list) and any(
            isinstance(a, str) and "chatgpt.com" in a for a in cmd
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


async def _record_one(provider: CodexOAuthProvider, scenario: Scenario) -> dict:
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
        raise RuntimeError(f"{scenario.sid}: no chatgpt.com subprocess call captured")
    if len(capturer.captures) > 1:
        print(f"[WARN] {scenario.sid}: {len(capturer.captures)} captures -- using last")

    capture = capturer.captures[-1]
    usage_obj = response.usage
    if usage_obj is None:
        usage_dict = None
    elif hasattr(usage_obj, "model_dump"):
        usage_dict = usage_obj.model_dump()
    else:
        # dataclass
        from dataclasses import asdict as _asdict
        from dataclasses import is_dataclass as _isdc
        usage_dict = _asdict(usage_obj) if _isdc(usage_obj) else dict(vars(usage_obj))
    tool_calls = response.tool_calls
    return {
        "scenario_id": scenario.sid,
        "prompt_system": scenario.system,
        "prompt_user": scenario.user,
        "response_text": response.content or "",
        "response_tool_call_count": len(tool_calls) if tool_calls else 0,
        "response_model": response.model,
        "usage": usage_dict,
        "capture": capture,  # raw bytes, pre-sanitize
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't actually call ChatGPT; fail fast if creds missing.")
    parser.add_argument("--scenario", default=None,
                        help="Record only one scenario by sid (e.g. codex-P01).")
    args = parser.parse_args()

    creds = read_codex_credentials()
    if not creds:
        print("ERROR: ~/.codex/auth.json not found or auth_mode != chatgpt", file=sys.stderr)
        return 1

    access_token = creds["access_token"]
    account_id = creds.get("account_id") or ""
    refresh_token = creds.get("refresh_token") or ""

    if args.dry_run:
        print(
            f"dry-run OK: access_token len={len(access_token)}, "
            f"account_id set={bool(account_id)}"
        )
        return 0

    secrets = {
        "CODEX_ACCESS_TOKEN": access_token,
        "CODEX_ACCOUNT_ID": account_id,
        "CODEX_REFRESH_TOKEN": refresh_token,
    }

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    provider = CodexOAuthProvider(model=MODEL)

    scenarios = [s for s in SCENARIOS if not args.scenario or s.sid == args.scenario]
    if not scenarios:
        print(f"No scenarios match --scenario={args.scenario}", file=sys.stderr)
        return 2

    manifest_entries: list[dict] = []
    for scenario in scenarios:
        print(f"[record] {scenario.sid} -- calling ChatGPT backend...")
        try:
            result = await _record_one(provider, scenario)
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
        sanitized_stdout = _sanitize(cap["stdout"], secrets)
        sanitized_stderr = _sanitize(cap["stderr"], secrets)
        sanitized_cmd = [
            re.sub(re.escape(v), f"<{k}>", arg) if isinstance(arg, str) else arg
            for arg in cap["cmd"]
            for k, v in secrets.items() if v
        ] if False else [
            # Keep cmd structure readable -- redact Authorization header value only
            re.sub(r"Bearer\s+\S+", "Bearer <CODEX_ACCESS_TOKEN>",
                   re.sub(r"ChatGPT-Account-Id:\s*\S+",
                          "ChatGPT-Account-Id: <CODEX_ACCOUNT_ID>", arg))
            if isinstance(arg, str) else arg
            for arg in cap["cmd"]
        ]

        fixture = {
            "scenario_id": result["scenario_id"],
            "recorded_with_model": MODEL,
            "prompt_system": result["prompt_system"],
            "prompt_user": result["prompt_user"],
            "response_preview": (result["response_text"] or "")[:200],
            "response_tool_call_count": result["response_tool_call_count"],
            "response_model": result["response_model"],
            "usage": result["usage"],
            "subprocess": {
                "cmd": sanitized_cmd,
                "returncode": cap["returncode"],
                "stdout_b64": sanitized_stdout.decode("utf-8", errors="replace"),
                "stderr_b64": sanitized_stderr.decode("utf-8", errors="replace"),
            },
        }
        fixture_path = FIXTURE_DIR / f"{scenario.sid}.json"
        fixture_path.write_text(json.dumps(fixture, indent=2, ensure_ascii=False), encoding="utf-8")

        # Hash the RESPONSE text (deterministic piece for byte-identical test)
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
        "provider": "codex_oauth",
        "model": MODEL,
        "auth_mode": "chatgpt",
        "entries": manifest_entries,
    }
    (FIXTURE_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[done] wrote {len(manifest_entries)} fixtures + manifest to {FIXTURE_DIR}")
    return 0 if all(e.get("recorded") for e in manifest_entries) else 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
