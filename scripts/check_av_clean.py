#!/usr/bin/env python3
"""Submit a built binary to VirusTotal and fail the build on detections (P0-05).

PyInstaller binaries frequently hit AV false positives. Running this
post-signing gives us a named list of flagged vendors that can be submitted
to their false-positive forms before release.

Env:
    VIRUSTOTAL_API_KEY   required; use a dedicated CI key
    VT_DETECTION_LIMIT   optional; max allowed detections (default 0)

Usage:
    python scripts/check_av_clean.py path/to/ds-agent-api.exe

Exit codes:
    0  clean (or detection count <= limit)
    1  over the limit
    2  configuration / upload error
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from pathlib import Path

VT_API = "https://www.virustotal.com/api/v3"
MAX_UPLOAD_MB = 32  # VT free/basic tier; larger files need /files/upload_url
POLL_INTERVAL = 15
POLL_TIMEOUT = 600


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch_report(requests_mod, headers: dict, digest: str) -> dict | None:
    """Return the existing VT report for this hash, if any."""
    resp = requests_mod.get(f"{VT_API}/files/{digest}", headers=headers, timeout=30)
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        sys.exit(f"[av] VT report lookup failed: {resp.status_code} {resp.text}")
    return resp.json()["data"]["attributes"]


def _upload_and_wait(requests_mod, headers: dict, path: Path) -> dict:
    """Upload the binary, poll the analysis endpoint, return stats."""
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        sys.exit(
            f"[av] File too large for direct upload ({size_mb:.1f} MB). "
            f"Use /files/upload_url for files > {MAX_UPLOAD_MB} MB."
        )

    with path.open("rb") as fh:
        resp = requests_mod.post(
            f"{VT_API}/files",
            headers=headers,
            files={"file": (path.name, fh)},
            timeout=120,
        )
    if resp.status_code != 200:
        sys.exit(f"[av] VT upload failed: {resp.status_code} {resp.text}")

    analysis_id = resp.json()["data"]["id"]
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        analysis = requests_mod.get(
            f"{VT_API}/analyses/{analysis_id}", headers=headers, timeout=30
        )
        if analysis.status_code != 200:
            continue
        attrs = analysis.json()["data"]["attributes"]
        if attrs.get("status") == "completed":
            return attrs

    sys.exit("[av] VT analysis timed out")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()

    api_key = os.environ.get("VIRUSTOTAL_API_KEY")
    if not api_key:
        print("[av] VIRUSTOTAL_API_KEY not set — skipping scan")
        sys.exit(0)

    try:
        import requests  # Optional dep; only needed when this runs.
    except ImportError:
        sys.exit(
            "[av] 'requests' is required. Install with: pip install requests"
        )

    limit = int(os.environ.get("VT_DETECTION_LIMIT", "0"))
    binary = args.binary
    if not binary.exists():
        sys.exit(f"[av] Binary not found: {binary}")

    headers = {"x-apikey": api_key}
    digest = _sha256(binary)
    print(f"[av] {binary.name} sha256={digest}")

    attrs = _fetch_report(requests, headers, digest)
    if attrs is None:
        print("[av] No existing report — uploading")
        attrs = _upload_and_wait(requests, headers, binary)

    stats = attrs.get("last_analysis_stats") or attrs.get("stats") or {}
    detections = int(stats.get("malicious", 0)) + int(stats.get("suspicious", 0))
    print(f"[av] VT stats: {stats}")

    if detections > limit:
        results = attrs.get("last_analysis_results") or attrs.get("results") or {}
        flagged = [
            name
            for name, r in results.items()
            if r.get("category") in {"malicious", "suspicious"}
        ]
        print(f"[av] Flagged vendors ({len(flagged)}): {', '.join(flagged)}")
        print(
            "[av] Submit false-positive reports before release. "
            "Set VT_DETECTION_LIMIT if a known FP is acceptable."
        )
        sys.exit(1)

    print(f"[av] PASS — detections {detections} <= limit {limit}")


if __name__ == "__main__":
    main()
