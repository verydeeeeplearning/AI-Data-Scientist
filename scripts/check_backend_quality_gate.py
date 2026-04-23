"""Run the backend baseline quality gate with agent-readable output.

The gate intentionally runs the lower-level contracts first:
1. Static import-boundary checks
2. Architecture tests
3. DS semantic contract tests

This keeps the Phase 6 contract lane grounded on the same baseline that the
development plan requires.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _tail_lines(text: str, *, limit: int = 40) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if len(lines) <= limit:
        return lines
    return lines[-limit:]


def _write_text(text: str, *, stream: Any) -> None:
    encoding = getattr(stream, "encoding", None) or "utf-8"
    safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
    stream.write(safe_text)
    if not safe_text.endswith("\n"):
        stream.write("\n")
    stream.flush()


def _print_section(name: str, command: list[str]) -> None:
    print(f"\n[{name}] {' '.join(command)}")


def _run_command(
    *,
    name: str,
    command: list[str],
    cwd: Path,
) -> dict[str, Any]:
    _print_section(name, command)
    result = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        _write_text(result.stdout, stream=sys.stdout)
    if result.stderr:
        _write_text(result.stderr, stream=sys.stderr)
    return {
        "name": name,
        "command": command,
        "exit_code": result.returncode,
        "status": "passed" if result.returncode == 0 else "failed",
        "stdout_tail": _tail_lines(result.stdout),
        "stderr_tail": _tail_lines(result.stderr),
    }


def _extract_ds_contract_summary(report: dict[str, Any]) -> dict[str, Any] | None:
    for line in report["stdout_tail"]:
        if not line.startswith("DS_CONTRACT_SUMMARY="):
            continue
        try:
            return json.loads(line.split("=", 1)[1])
        except json.JSONDecodeError:
            return None
    return None


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    py = sys.executable
    architecture_basetemp = repo_root / ".tmp" / "pytest-architecture-gate"
    architecture_cache = architecture_basetemp / ".cache"
    architecture_basetemp.mkdir(parents=True, exist_ok=True)
    architecture_cache.mkdir(parents=True, exist_ok=True)

    reports = [
        _run_command(
            name="import_contracts",
            command=[py, "scripts/check_import_contracts.py"],
            cwd=repo_root,
        ),
        _run_command(
            name="architecture_tests",
            command=[
                py,
                "-m",
                "pytest",
                "tests/unit/architecture",
                "-q",
                "--tb=short",
                f"--basetemp={architecture_basetemp}",
                "-o",
                f"cache_dir={architecture_cache}",
            ],
            cwd=repo_root,
        ),
        _run_command(
            name="ds_semantic_contracts",
            command=[py, "scripts/check_ds_contracts.py"],
            cwd=repo_root,
        ),
    ]

    summary = {
        "suite": "backend_quality_gate",
        "status": "passed" if all(report["exit_code"] == 0 for report in reports) else "failed",
        "checks": {
            report["name"]: {
                "status": report["status"],
                "exit_code": report["exit_code"],
                "command": report["command"],
                "stdout_tail": report["stdout_tail"],
                "stderr_tail": report["stderr_tail"],
                "ds_contract_summary": (
                    _extract_ds_contract_summary(report)
                    if report["name"] == "ds_semantic_contracts"
                    else None
                ),
            }
            for report in reports
        },
    }

    print(f"BACKEND_QUALITY_GATE_STATUS={summary['status']}")
    print("BACKEND_QUALITY_GATE_SUMMARY=" + json.dumps(summary, sort_keys=True))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
