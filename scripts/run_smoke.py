#!/usr/bin/env python3
"""Run the packaged-binary smoke suite locally.

Locates ``dist/ds-agent-backend/ds-agent-api(.exe)`` (or ``$PACKAGED_BINARY_PATH``)
and invokes ``pytest tests/smoke``. Builds the backend first when ``--build``
is passed.

Usage:
    python scripts/run_smoke.py            # use existing binary
    python scripts/run_smoke.py --build    # rebuild binary first
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BINARY = ROOT / "dist" / "ds-agent-backend" / (
    "ds-agent-api.exe" if sys.platform == "win32" else "ds-agent-api"
)


def _build_backend() -> None:
    cmd = [sys.executable, str(ROOT / "scripts" / "build_backend.py"), "--clean"]
    print(f"[smoke] building backend: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print("[smoke] backend build failed", file=sys.stderr)
        sys.exit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run packaged smoke suite")
    parser.add_argument(
        "--build",
        action="store_true",
        help="Rebuild backend with PyInstaller before running smoke tests.",
    )
    parser.add_argument(
        "--binary",
        type=Path,
        help="Override binary path (sets PACKAGED_BINARY_PATH).",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional args forwarded to pytest.",
    )
    args = parser.parse_args()

    if args.build:
        _build_backend()

    binary = args.binary or DEFAULT_BINARY
    if not binary.exists():
        print(
            f"[smoke] binary not found at {binary}. "
            "Pass --build or set --binary / PACKAGED_BINARY_PATH.",
            file=sys.stderr,
        )
        sys.exit(2)

    env = {**os.environ, "PACKAGED_BINARY_PATH": str(binary)}
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/smoke",
        "-v",
        "-m",
        "smoke",
        *args.pytest_args,
    ]
    print(f"[smoke] running: {' '.join(cmd)} (binary={binary})")
    result = subprocess.run(cmd, cwd=str(ROOT), env=env)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
