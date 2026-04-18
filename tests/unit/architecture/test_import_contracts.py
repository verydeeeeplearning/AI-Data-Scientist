from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_static_import_contracts_are_clean() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_import_contracts.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "import contracts: ok" in result.stdout
