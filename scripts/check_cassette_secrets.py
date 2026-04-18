#!/usr/bin/env python
"""CI hook: grep-based guard that ensures no API key / bearer token leaks into
committed VCR.py cassettes.

Scope:
    tests/fixtures/llm_cassettes/*.yaml
    tests/fixtures/llm_cassettes/**/*.json   (Codex subprocess fixtures, S22)

Exit codes:
    0 — all cassettes clean.
    1 — at least one leak detected. Cassette paths + matched lines printed.
    2 — directory missing (no cassettes to scan). Non-fatal on PRs without cassette changes,
        but CI configures this script to gate only when cassette files are touched.

Patterns (any match → fail):
    - ``sk-proj-...``            (OpenAI project keys, new format 2024+)
    - ``sk-ant-...``             (Anthropic keys)
    - ``sk-[A-Za-z0-9_\\-]{30,}``  (generic long sk- tokens)
    - ``AIzaSy[A-Za-z0-9_\\-]{30,}`` (Google API keys, incl. Gemini)
    - ``authorization: bearer <TOKEN>`` where TOKEN starts with anything other
      than ``REDACTED`` (i.e. the filter_headers VCR guard was bypassed).

Usage:
    python scripts/check_cassette_secrets.py [cassette_dir]

The optional argument overrides the default ``tests/fixtures/llm_cassettes``.

Design note:
    This runs *after* VCR.py's filter_headers/filter_post_data_parameters
    filters. Defense-in-depth: if the filters ever regress (VCR.py update,
    unexpected header name, SDK changes), this grep catches it before the
    cassette lands in git.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "llm_cassettes"

# Any match across these patterns = leak.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "openai_project_key",
        re.compile(r"sk-proj-[A-Za-z0-9_\-]{10,}"),
    ),
    (
        "anthropic_key",
        re.compile(r"sk-ant-(?:api\d{2}-)?[A-Za-z0-9_\-]{20,}"),
    ),
    (
        "generic_long_sk",
        # Match sk- followed by >=30 non-space/non-quote chars. Avoid catching
        # our own redaction token "sk-replay-dummy" (15 chars, safely shorter).
        re.compile(r"sk-(?!replay-dummy\b)(?!ant-)(?!proj-)[A-Za-z0-9_\-]{30,}"),
    ),
    (
        "google_api_key",
        re.compile(r"AIzaSy[A-Za-z0-9_\-]{30,}"),
    ),
    (
        "authorization_bearer_not_redacted",
        # header appears in YAML as "- Bearer sk-..." or "Authorization: Bearer ..."
        # Pass if token is "REDACTED" or a `<PLACEHOLDER>` (angle-bracket form).
        re.compile(r"[Aa]uthorization:\s*-?\s*Bearer\s+(?!REDACTED\b)(?!<[A-Z_]+>)[^\s\"']+"),
    ),
    (
        "bearer_list_form",
        # VCR serializes headers as lists: `Authorization: - Bearer sk-...`
        re.compile(r"-\s*Bearer\s+(?!REDACTED\b)(?!<[A-Z_]+>)[A-Za-z0-9_\-\.]{20,}"),
    ),
    (
        "jwt_eyJ",
        # JWTs (Codex access_token, Gemini id_token) have form eyJ...eyJ...sig
        # Must not match our <REDACTED_JWT> placeholder or <CODEX_ACCESS_TOKEN>.
        re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
    ),
    (
        "codex_chatgpt_account_id",
        # account_id is a UUID in auth.json. If it leaks verbatim, catch it.
        re.compile(r"ChatGPT-Account-Id:\s*(?!<CODEX_ACCOUNT_ID>)[0-9a-fA-F\-]{30,}"),
    ),
]


def scan_file(path: Path) -> list[tuple[int, str, str, str]]:
    """Return list of (line_no, pattern_name, matched_substring, full_line)."""
    findings: list[tuple[int, str, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"ERROR: cannot read {path}: {exc}", file=sys.stderr)
        return findings

    for lineno, line in enumerate(text.splitlines(), start=1):
        for name, pat in _SECRET_PATTERNS:
            m = pat.search(line)
            if m:
                findings.append((lineno, name, m.group(0), line.strip()))
    return findings


def main(argv: list[str]) -> int:
    target_dir = Path(argv[1]).resolve() if len(argv) > 1 else DEFAULT_DIR
    if not target_dir.exists():
        print(f"[check_cassette_secrets] directory missing: {target_dir} — nothing to scan")
        return 2

    cassettes = (
        sorted(target_dir.glob("*.yaml"))
        + sorted(target_dir.glob("*.yml"))
        + sorted(target_dir.rglob("*.json"))
    )
    if not cassettes:
        print(f"[check_cassette_secrets] no cassette files in {target_dir}")
        return 0

    total_leaks = 0
    for cass in cassettes:
        findings = scan_file(cass)
        if not findings:
            print(f"  OK  {cass.relative_to(target_dir.parent.parent.parent)}")
            continue
        print(f"LEAK  {cass.relative_to(target_dir.parent.parent.parent)}")
        for lineno, name, match, line in findings:
            # Print max 80 chars of matched substring for safety (don't want to
            # echo the leaked secret itself in full). Show the pattern name.
            redacted_match = match[:12] + "...<truncated>" if len(match) > 12 else match
            print(f"     line {lineno} [{name}]: {redacted_match}  -- in: {line[:120]}")
            total_leaks += 1

    if total_leaks:
        print(f"\nFAIL: {total_leaks} leak(s) detected across {len(cassettes)} cassette file(s).")
        print("Action: filter the offending header/body value via VCR.py filter_headers,")
        print("delete the compromised cassette, then re-record.")
        return 1

    print(f"\nPASS: {len(cassettes)} cassette(s) scanned, 0 leaks.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
