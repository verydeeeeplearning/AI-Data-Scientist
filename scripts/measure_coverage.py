"""Measure pytest coverage for ds_agent (KAG-1 resolution).

Runs pytest against ``tests/unit/`` with coverage measurement and writes:

    .tmp/qa_phase2/coverage_terminal.txt
    .tmp/qa_phase2/html/index.html

The coverage threshold (``fail_under = 78``) is enforced by ``pyproject.toml``;
this script exits non-zero if it is not met.

Usage::

    python scripts/measure_coverage.py

Known limitation: Windows ``.tmp/pytest`` teardown flake (see HANDOFF §4.5) can
leave ~18 unrelated failures in `test_file_ops.py`, `test_telegram_runner.py`,
`test_integration_tools.py`, and `test_decision_os_scheduler.py`. These are
scope-orthogonal to coverage measurement and are tracked as ENV-1.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / ".tmp" / "qa_phase2"
HTML_DIR = OUT_DIR / "html"
TERMINAL_REPORT = OUT_DIR / "coverage_terminal.txt"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/unit/",
        "--cov=src/ds_agent",
        "--cov-report=term",
        "--tb=no",
        "-q",
    ]
    result = subprocess.run(pytest_cmd, cwd=REPO_ROOT, check=False)

    # Persist HTML + terminal reports even when the pytest run has partial flake.
    subprocess.run(
        [sys.executable, "-m", "coverage", "html", "-d", str(HTML_DIR)],
        cwd=REPO_ROOT,
        check=False,
    )
    with TERMINAL_REPORT.open("w", encoding="utf-8") as fp:
        subprocess.run(
            [sys.executable, "-m", "coverage", "report"],
            cwd=REPO_ROOT,
            stdout=fp,
            stderr=subprocess.STDOUT,
            check=False,
        )

    print(f"[coverage] HTML: {HTML_DIR.relative_to(REPO_ROOT)}/index.html")
    print(f"[coverage] Terminal: {TERMINAL_REPORT.relative_to(REPO_ROOT)}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
