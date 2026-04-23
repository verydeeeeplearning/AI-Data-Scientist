"""Record 3 OpenAI chat.completions cassettes for S16 parity replay.

Run ONCE per provider API signature change:
    export OPENAI_API_KEY=sk-proj-...
    python scripts/parity_harness/record_llm_cassettes.py

After success (3 cassettes written to tests/fixtures/llm_cassettes/),
run:

    python scripts/check_cassette_secrets.py

to verify zero secret leakage. The sanitization is enforced by VCR.py
filter_headers/filter_post_data_parameters at record time; the grep
check is belt-and-braces defense in depth.

CI: this script is NOT run in CI. CI enforces VCR_RECORD_MODE=none,
which makes any attempted re-record fail fast.

Rationale for direct harness-side recording (instead of via the
packaged backend subprocess):
    VCR.py only intercepts HTTP within the *same* Python process. The
    backend is a PyInstaller subprocess, so VCR cannot transparently
    capture its openai SDK traffic. We therefore record the response
    bytes directly from a harness-owned AsyncOpenAI client and later
    REPLAY those bytes to the backend via a local HTTP proxy. See
    Docs/rfc/RFC_2026-04_llm_record_replay.md §2.2 for the full rationale.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import vcr  # type: ignore[import-untyped]
import yaml  # type: ignore[import-untyped]

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.parity_harness.scenarios import ALL_SCENARIOS, Scenario

CASSETTE_DIR = REPO / "tests" / "fixtures" / "llm_cassettes"
CASSETTE_DIR.mkdir(parents=True, exist_ok=True)

# Single-digit $ budget guard — check by recording model + token ceiling.
MODEL = "gpt-4o-mini"
MAX_COMPLETION_TOKENS = 256  # keep replies short; this sprint validates transport parity, not answer quality.
TEMPERATURE = 0.0  # deterministic (still recorded, so replay is by definition byte-identical)


def _make_vcr() -> vcr.VCR:
    """Build a VCR instance with strict secret filtering."""
    return vcr.VCR(
        cassette_library_dir=str(CASSETTE_DIR),
        record_mode="once",  # first run records, subsequent runs replay (no real API call)
        match_on=["method", "scheme", "host", "port", "path", "body"],
        filter_headers=[
            ("authorization", "Bearer REDACTED"),
            ("Authorization", "Bearer REDACTED"),
            ("x-api-key", "REDACTED"),
            ("X-Api-Key", "REDACTED"),
            ("openai-organization", "REDACTED"),
            ("OpenAI-Organization", "REDACTED"),
            ("openai-project", "REDACTED"),
            ("OpenAI-Project", "REDACTED"),
            ("cookie", "REDACTED"),
            ("Cookie", "REDACTED"),
        ],
        filter_query_parameters=[("api_key", "REDACTED"), ("key", "REDACTED")],
        filter_post_data_parameters=[("api_key", "REDACTED")],
        decode_compressed_response=True,
    )


@dataclass(frozen=True)
class RecordingTask:
    """One recording job."""

    scenario: Scenario
    cassette_name: str


def _build_tasks() -> list[RecordingTask]:
    tasks: list[RecordingTask] = []
    for sc in ALL_SCENARIOS:
        # P-01 → scenario_P01.yaml
        cname = f"scenario_{sc.scenario_id.replace('-', '')}.yaml"
        tasks.append(RecordingTask(scenario=sc, cassette_name=cname))
    return tasks


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------
# The prompt shape mirrors what a production DSAgent turn would send:
#   system: role framing
#   user: scenario goal (exactly as scenarios.py defines)
#
# We keep it short: the sprint is proving transport+parity, not answer quality.
# The replay proxy matches on scenario prompt content, so changing this text
# later WILL invalidate the cassette — that is the intended trade-off.

SYSTEM_PROMPT = (
    "당신은 DS Agent의 LLM 응답 녹화용 경량 assistant입니다. "
    "한국어로 2~3문장으로 짧게 접수 확인과 다음 단계만 제시하세요. "
    "코드, 숫자 결과, 날짜, 세션 ID를 포함하지 마세요."
)


def _user_prompt(scenario: Scenario) -> str:
    return scenario.goal


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------

def _check_env() -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        print("FATAL: OPENAI_API_KEY is not set. Set it in the CURRENT SHELL only, do not commit.", file=sys.stderr)
        sys.exit(2)
    if not key.startswith("sk-"):
        print("FATAL: OPENAI_API_KEY does not look like an OpenAI key.", file=sys.stderr)
        sys.exit(2)
    return key


async def _record_one(task: RecordingTask, my_vcr: vcr.VCR) -> dict:
    """Record one cassette.  Returns a small summary dict (no secrets)."""
    # lazy import inside the function so the SDK object is constructed AFTER
    # VCR.py has had a chance to patch the HTTP stack.
    import openai

    # Force HTTPS → the real provider. OPENAI_BASE_URL is honored if set, but
    # for RECORDING we deliberately rely on the default api.openai.com.
    client = openai.AsyncOpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        timeout=60.0,
        max_retries=0,  # deterministic recording
    )

    cassette_path = CASSETTE_DIR / task.cassette_name
    # Overwrite mode: delete existing file so record_mode='once' will record fresh.
    # If the operator wants to use an existing cassette, they can skip running this script.
    if cassette_path.exists():
        cassette_path.unlink()

    summary = {
        "scenario_id": task.scenario.scenario_id,
        "cassette": str(cassette_path.relative_to(REPO)),
        "model": MODEL,
        "recorded": False,
        "error": None,
        "response_content_preview": "",
        "usage_tokens": None,
    }

    with my_vcr.use_cassette(task.cassette_name):
        try:
            resp = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _user_prompt(task.scenario)},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_COMPLETION_TOKENS,
            )
            content = resp.choices[0].message.content or ""
            summary["response_content_preview"] = content[:160]
            summary["usage_tokens"] = {
                "prompt": resp.usage.prompt_tokens if resp.usage else None,
                "completion": resp.usage.completion_tokens if resp.usage else None,
                "total": resp.usage.total_tokens if resp.usage else None,
            }
            summary["recorded"] = True
        except Exception as exc:  # pragma: no cover — fail loud
            summary["error"] = f"{type(exc).__name__}: {exc}"

    return summary


# ---------------------------------------------------------------------------
# Post-record response header sanitization (defense in depth)
# ---------------------------------------------------------------------------
#
# VCR.py's filter_headers option sanitizes REQUEST headers. Response headers
# from OpenAI include:
#   - openai-organization  (org ID for the billing account)
#   - openai-project       (project ID)
#   - set-cookie           (Cloudflare __cf_bm tracking cookie)
#   - cf-ray               (Cloudflare ray ID; not a secret but PII-adjacent)
#   - x-request-id         (provider-side request ID; not a secret but
#                           uniquely identifies our account's traffic)
#
# None of these are bearer tokens, but they leak account identity. We
# redact them explicitly after VCR writes the cassette.
_RESPONSE_HEADERS_TO_REDACT = {
    "openai-organization",
    "openai-project",
    "set-cookie",
    "cf-ray",
    "x-request-id",
}


def _sanitize_response_headers(cassette_path: Path) -> int:
    """Rewrite cassette file, redacting sensitive response headers.

    Returns count of headers redacted.
    """
    with cassette_path.open("r", encoding="utf-8") as fh:
        data: Any = yaml.safe_load(fh)
    redacted = 0
    for interaction in data.get("interactions", []) or []:
        resp = interaction.get("response", {}) or {}
        headers = resp.get("headers", {}) or {}
        for key in list(headers.keys()):
            if key.lower() in _RESPONSE_HEADERS_TO_REDACT:
                headers[key] = ["REDACTED"]
                redacted += 1
    with cassette_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, default_flow_style=False, allow_unicode=True)
    return redacted


async def _main_async() -> int:
    _check_env()
    my_vcr = _make_vcr()
    tasks = _build_tasks()
    print(f"[record_llm_cassettes] recording {len(tasks)} cassette(s) into {CASSETTE_DIR}")
    summaries: list[dict] = []
    for t in tasks:
        print(f"  - {t.scenario.scenario_id}  ->  {t.cassette_name}")
        s = await _record_one(t, my_vcr)
        # Post-record response header sanitization
        cassette_path = CASSETTE_DIR / t.cassette_name
        if cassette_path.exists():
            redacted = _sanitize_response_headers(cassette_path)
            s["response_headers_redacted"] = redacted
        summaries.append(s)
        if not s["recorded"]:
            print(f"    FAIL: {s['error']}")
        else:
            preview = str(s["response_content_preview"])[:80].replace("\n", " ")
            usage = s["usage_tokens"] or {}
            print(
                f"    OK  preview={preview!r}  tokens={usage.get('total')} "
                f"(prompt={usage.get('prompt')} completion={usage.get('completion')}) "
                f"response_headers_redacted={s.get('response_headers_redacted', 0)}"
            )
    # Persist a manifest (no secrets; includes tokens for cost audit)
    manifest_path = CASSETTE_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps({"model": MODEL, "cassettes": summaries}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[record_llm_cassettes] manifest: {manifest_path}")

    all_ok = all(s["recorded"] for s in summaries)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main_async()))
