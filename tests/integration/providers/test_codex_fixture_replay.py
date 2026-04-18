"""Replay recorded Codex OAuth subprocess fixtures byte-identically (S22).

Fixtures were recorded by scripts/parity_harness/record_codex_fixture.py
against real ``~/.codex/auth.json`` + ``chatgpt.com/backend-api``. Here we
monkeypatch ``subprocess.run`` so the provider re-parses the recorded raw
stdout bytes and re-constructs the same LLMResponse. We hash the response
text and compare against the manifest's recorded SHA-256 — a bitwise
"cassette replay byte-identical" guarantee with no external network calls.

Coverage: 3-way LLM connection model §1.1 — OAuth tier (Codex CLI).
Companion to VCR cassette tests for the API tier (S16) and the pending
Gemini CLI subprocess fixture (Phase 4).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.providers.codex_oauth import CodexOAuthProvider

FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "llm_cassettes"
    / "codex"
)
MANIFEST = FIXTURE_DIR / "manifest.json"


def _manifest_entries() -> list[dict]:
    if not MANIFEST.exists():
        return []
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return [e for e in data.get("entries", []) if e.get("recorded")]


@pytest.fixture
def codex_subprocess_replay(monkeypatch, request):
    """Replace subprocess.run for chatgpt.com calls with fixture playback.

    Parametrized via ``request.param`` = scenario_id. Non-chatgpt.com
    subprocess calls pass through to the real subprocess.run.
    """
    scenario_id: str = request.param
    fixture_path = FIXTURE_DIR / f"{scenario_id}.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    canned_stdout = fixture["subprocess"]["stdout_b64"].encode("utf-8")
    canned_stderr = fixture["subprocess"]["stderr_b64"].encode("utf-8")
    canned_rc = int(fixture["subprocess"]["returncode"])

    real_run = subprocess.run

    def _fake_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args")
        if isinstance(cmd, list) and any(
            isinstance(a, str) and "chatgpt.com" in a for a in cmd
        ):
            class _Result:
                returncode = canned_rc
                stdout = canned_stdout
                stderr = canned_stderr
            return _Result()
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    return fixture


@pytest.mark.parametrize(
    "codex_subprocess_replay",
    [e["scenario_id"] for e in _manifest_entries()] or ["__no_fixtures__"],
    indirect=True,
)
@pytest.mark.asyncio
async def test_codex_replay_byte_identical(codex_subprocess_replay):
    fixture = codex_subprocess_replay
    if fixture is None or fixture.get("scenario_id") == "__no_fixtures__":
        pytest.skip("Codex fixtures not recorded (no manifest entries)")

    # Use a fake access_token/account_id — replay doesn't need real creds
    # because subprocess.run is intercepted before any HTTP happens.
    provider = CodexOAuthProvider(
        model=fixture["recorded_with_model"],
        access_token="fake-replay-token",
    )
    # Override account_id (constructor reads from ~/.codex/auth.json otherwise)
    provider._account_id = "fake-replay-account"

    response = await provider.chat(
        messages=[
            ChatMessage(role=Role.SYSTEM, content=fixture["prompt_system"]),
            ChatMessage(role=Role.USER, content=fixture["prompt_user"]),
        ],
    )

    # Compare response text hash against manifest
    manifest_entries = _manifest_entries()
    sid = fixture["scenario_id"]
    expected_sha = next(
        (e["response_sha256"] for e in manifest_entries if e["scenario_id"] == sid),
        None,
    )
    assert expected_sha, f"manifest missing SHA for {fixture['scenario_id']}"

    actual_sha = hashlib.sha256((response.content or "").encode("utf-8")).hexdigest()
    assert actual_sha == expected_sha, (
        f"Codex replay drift for {fixture['scenario_id']}: "
        f"expected {expected_sha}, got {actual_sha}"
    )


def test_manifest_exists_and_nonempty():
    assert MANIFEST.exists(), f"{MANIFEST} must exist (run record_codex_fixture.py)"
    entries = _manifest_entries()
    assert entries, "manifest has zero recorded entries"
    assert len(entries) >= 1


def test_every_fixture_is_sanitized():
    """Cheap guard: fixture content must not contain raw Bearer tokens.

    Stronger check lives in scripts/check_cassette_secrets.py; this one
    runs in-process so failures surface in the normal test run.
    """
    for entry in _manifest_entries():
        fx = json.loads((FIXTURE_DIR / f"{entry['scenario_id']}.json").read_text(encoding="utf-8"))
        cmd = fx["subprocess"]["cmd"]
        joined = " ".join(str(a) for a in cmd)
        assert "<CODEX_ACCESS_TOKEN>" in joined, f"cmd for {entry['scenario_id']} not sanitized"
        # Should NOT contain a raw eyJ... JWT
        assert "Bearer eyJ" not in joined, f"{entry['scenario_id']}: raw JWT leaked in cmd"
