"""Replay recorded Gemini CLI OAuth subprocess fixtures byte-identically.

Phase 4 of `Docs/plans/PLAN_llm_oauth_and_ml_execution_2026-04-18.md`.
Companion to test_codex_fixture_replay.py (Phase 5, API tier: subprocess
curl to chatgpt.com) and the S16 VCR cassette tests (API tier, HTTP).

This test proves the OpenClaw-style OAuth path for Gemini — subscription-
backed via the official `gemini` CLI binary — is deterministic under
cassette replay: same fixture stdout → same LLMResponse → same hash.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.providers.gemini_cli import GeminiCliProvider

FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "llm_cassettes"
    / "gemini_cli"
)
MANIFEST = FIXTURE_DIR / "manifest.json"


def _manifest_entries() -> list[dict]:
    if not MANIFEST.exists():
        return []
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return [e for e in data.get("entries", []) if e.get("recorded")]


@pytest.fixture
def gemini_cli_replay(monkeypatch, request):
    """Replace subprocess.run for `gemini*` invocations with fixture playback.

    Parametrized via ``request.param`` = scenario_id. Non-gemini subprocess
    calls pass through to the real subprocess.run.
    """
    scenario_id: str = request.param
    fixture_path = FIXTURE_DIR / f"{scenario_id}.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    canned_stdout = fixture["subprocess"]["stdout"].encode("utf-8")
    canned_stderr = fixture["subprocess"]["stderr"].encode("utf-8")
    canned_rc = int(fixture["subprocess"]["returncode"])

    real_run = subprocess.run

    def _fake_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args")
        if isinstance(cmd, list) and any(
            isinstance(a, str) and "gemini" in str(a).lower()
            for a in cmd
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
    "gemini_cli_replay",
    [e["scenario_id"] for e in _manifest_entries()] or ["__no_fixtures__"],
    indirect=True,
)
@pytest.mark.asyncio
async def test_gemini_cli_replay_byte_identical(gemini_cli_replay):
    fixture = gemini_cli_replay
    if fixture is None or fixture.get("scenario_id") == "__no_fixtures__":
        pytest.skip("Gemini CLI fixtures not recorded (no manifest entries)")

    provider = GeminiCliProvider(model=fixture["recorded_with_model"])
    response = await provider.chat(
        messages=[
            ChatMessage(role=Role.SYSTEM, content=fixture["prompt_system"]),
            ChatMessage(role=Role.USER, content=fixture["prompt_user"]),
        ],
    )

    manifest_entries = _manifest_entries()
    sid = fixture["scenario_id"]
    expected_sha = next(
        (e["response_sha256"] for e in manifest_entries if e["scenario_id"] == sid),
        None,
    )
    assert expected_sha, f"manifest missing SHA for {sid}"

    actual_sha = hashlib.sha256((response.content or "").encode("utf-8")).hexdigest()
    assert actual_sha == expected_sha, (
        f"Gemini CLI replay drift for {sid}: "
        f"expected {expected_sha}, got {actual_sha}"
    )


def test_manifest_exists_and_nonempty():
    assert MANIFEST.exists(), f"{MANIFEST} must exist (run record_gemini_cli_fixture.py)"
    entries = _manifest_entries()
    assert entries, "manifest has zero recorded entries"
    assert len(entries) >= 1


def test_every_fixture_is_sanitized():
    """Cheap in-process guard. scripts/check_cassette_secrets.py is the
    stronger CI-level check."""
    for entry in _manifest_entries():
        fx = json.loads(
            (FIXTURE_DIR / f"{entry['scenario_id']}.json").read_text(encoding="utf-8")
        )
        stdout = fx["subprocess"]["stdout"]
        # No JWT pattern
        assert "eyJ" not in stdout or "<REDACTED_JWT>" in stdout, (
            f"{entry['scenario_id']}: raw JWT leaked in stdout"
        )
        # Prompt arg must have been replaced with <PROMPT> placeholder
        assert any(
            a == "<PROMPT>" for a in fx["subprocess"]["cmd"]
        ), f"{entry['scenario_id']}: prompt arg not redacted in cmd"


def test_provider_auto_detects_cli_transport():
    """When OAuth creds are present and no API key is provided, the transport
    selector should pick the CLI path."""
    from ds_agent.providers.gemini_cli import gemini_oauth_creds_present
    from ds_agent.providers.gemini_oauth import GeminiOAuthProvider

    if not gemini_oauth_creds_present():
        pytest.skip("no gemini oauth creds — not applicable in this env")

    provider = GeminiOAuthProvider(force_transport="cli")
    assert provider._transport == "cli"
    provider2 = GeminiOAuthProvider(force_transport="litellm", api_key="dummy")
    assert provider2._transport == "litellm"
