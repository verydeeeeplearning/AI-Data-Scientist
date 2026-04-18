"""Check mypy errors against a frozen baseline.

Purpose
-------
The codebase has pre-existing mypy errors (see
``Docs/plans/PLAN_post_qa_risk_mitigation_2026-04-17.md`` Phase 1b for rationale).
Fixing all 383 at once is high-risk; instead, we freeze the current state in
``mypy-baseline.json`` and fail CI only when **new** errors appear on top of it.

Existing errors can be cleaned up incrementally via layer-scoped follow-ups; the
baseline is regenerated with ``--update`` when entries are legitimately resolved.

Usage
-----
::

    # Check (default): compare current mypy run against baseline.
    #   Exit 0 = no new errors (baseline may have shrunk, which is fine).
    #   Exit 1 = new errors detected, printed with context.
    python scripts/check_mypy_baseline.py

    # Regenerate the baseline from scratch (after intentional fixes).
    python scripts/check_mypy_baseline.py --update

The script targets ``src/ds_agent`` -- adjust ``MYPY_TARGET`` if the scope changes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "mypy-baseline.json"
MYPY_TARGET = "src/ds_agent"

# Example line (truncated):
#   src\ds_agent\api\app.py:27: error: Item "X" has no attribute "Y"  [union-attr]
_LINE_PATTERN = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):\s*error:\s*(?P<message>.*?)\s*\[(?P<code>[a-z0-9\-]+)\]\s*$"
)


@dataclass(frozen=True, slots=True)
class MypyError:
    """One mypy error line normalized for comparison."""

    file: str  # forward-slash normalized, repo-relative
    line: int
    code: str
    message: str

    def key(self) -> tuple[str, int, str, str]:
        return (self.file, self.line, self.code, self.message)

    def to_dict(self) -> dict[str, object]:
        return {"file": self.file, "line": self.line, "code": self.code, "message": self.message}

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> MypyError:
        return cls(
            file=str(raw["file"]),
            line=int(raw["line"]),  # type: ignore[arg-type]
            code=str(raw["code"]),
            message=str(raw["message"]),
        )


def _normalize_path(raw: str) -> str:
    return raw.replace("\\", "/").strip()


def _parse_mypy_output(output: str) -> list[MypyError]:
    errors: list[MypyError] = []
    for raw_line in output.splitlines():
        match = _LINE_PATTERN.match(raw_line)
        if match is None:
            continue
        errors.append(
            MypyError(
                file=_normalize_path(match.group("file")),
                line=int(match.group("line")),
                code=match.group("code"),
                message=match.group("message"),
            )
        )
    return errors


def _run_mypy() -> str:
    result = subprocess.run(
        [sys.executable, "-m", "mypy", MYPY_TARGET],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # mypy prints errors to stdout; stderr usually empty.
    return result.stdout + result.stderr


def _load_baseline(path: Path) -> list[MypyError]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("errors", [])
    return [MypyError.from_dict(entry) for entry in entries]


def _write_baseline(path: Path, errors: Iterable[MypyError]) -> None:
    ordered = sorted(errors, key=lambda e: (e.file, e.line, e.code, e.message))
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool": "mypy",
        "target": MYPY_TARGET,
        "total_errors": len(ordered),
        "errors": [e.to_dict() for e in ordered],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _report_delta(
    current: list[MypyError],
    baseline: list[MypyError],
) -> tuple[list[MypyError], list[MypyError]]:
    current_keys = {e.key(): e for e in current}
    baseline_keys = {e.key(): e for e in baseline}
    new_errors = [current_keys[k] for k in current_keys if k not in baseline_keys]
    resolved = [baseline_keys[k] for k in baseline_keys if k not in current_keys]
    return new_errors, resolved


def cmd_check() -> int:
    output = _run_mypy()
    current = _parse_mypy_output(output)
    baseline = _load_baseline(BASELINE_PATH)

    if not baseline:
        print(f"[mypy-baseline] No baseline at {BASELINE_PATH.relative_to(REPO_ROOT)}.")
        print("[mypy-baseline] Run with --update to create one.")
        return 1

    new_errors, resolved = _report_delta(current, baseline)

    print(
        f"[mypy-baseline] baseline={len(baseline)} current={len(current)} "
        f"new={len(new_errors)} resolved={len(resolved)}"
    )

    if resolved:
        print(
            f"[mypy-baseline] {len(resolved)} baseline entries no longer present "
            "(not a failure)."
        )
        print("[mypy-baseline] Consider running --update to shrink the baseline.")

    if new_errors:
        print(f"[mypy-baseline] {len(new_errors)} NEW error(s) detected on top of baseline:")
        for err in sorted(new_errors, key=lambda e: (e.file, e.line, e.code)):
            print(f"  {err.file}:{err.line}: [{err.code}] {err.message}")
        return 1

    print("[mypy-baseline] OK -- no new errors beyond baseline.")
    return 0


def cmd_update() -> int:
    output = _run_mypy()
    current = _parse_mypy_output(output)
    _write_baseline(BASELINE_PATH, current)
    print(
        f"[mypy-baseline] Wrote {len(current)} error(s) to "
        f"{BASELINE_PATH.relative_to(REPO_ROOT)}."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Regenerate mypy-baseline.json from the current mypy run",
    )
    args = parser.parse_args(argv)
    return cmd_update() if args.update else cmd_check()


if __name__ == "__main__":
    sys.exit(main())
