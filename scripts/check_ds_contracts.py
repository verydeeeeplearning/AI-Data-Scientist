"""Run backend DS semantic contract tests and emit an agent-readable summary."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import pytest


class ContractReportPlugin:
    def __init__(self) -> None:
        self.tests_collected = 0
        self.deselected = 0
        self.passed: set[str] = set()
        self.failed: set[str] = set()
        self.skipped: set[str] = set()
        self.xfailed: set[str] = set()
        self.xpassed: set[str] = set()
        self.collection_failures: set[str] = set()
        self.durations_s: dict[str, float] = {}

    def pytest_collection_finish(self, session: Any) -> None:
        self.tests_collected = session.testscollected

    def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
        self.tests_collected = session.testscollected

    def pytest_deselected(self, items: list[Any]) -> None:
        self.deselected += len(items)

    def pytest_collectreport(self, report: Any) -> None:
        if report.failed:
            self.collection_failures.add(getattr(report, "nodeid", str(report.fspath)))

    def pytest_runtest_logreport(self, report: Any) -> None:
        nodeid = report.nodeid
        wasxfail = getattr(report, "wasxfail", None)
        if report.when == "call":
            self.durations_s[nodeid] = round(report.duration, 4)

        if report.failed:
            if wasxfail:
                self.xfailed.add(nodeid)
            else:
                self.failed.add(nodeid)
            return
        if report.passed and report.when == "call":
            if wasxfail:
                self.xpassed.add(nodeid)
            else:
                self.passed.add(nodeid)
            return
        if report.skipped and report.when in {"setup", "call"}:
            if wasxfail:
                self.xfailed.add(nodeid)
            else:
                self.skipped.add(nodeid)

    def build_summary(self, exit_code: int) -> dict[str, Any]:
        return {
            "suite": "backend_ds_semantic_contracts",
            "target": "tests/contract",
            "status": "passed" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "collected": self.tests_collected,
            "selected": self.tests_collected - self.deselected,
            "deselected": self.deselected,
            "counts": {
                "passed": len(self.passed),
                "failed": len(self.failed),
                "skipped": len(self.skipped),
                "xfailed": len(self.xfailed),
                "xpassed": len(self.xpassed),
                "collection_failures": len(self.collection_failures),
            },
            "failures": sorted(self.failed),
            "collection_failures": sorted(self.collection_failures),
            "durations_s": {
                nodeid: self.durations_s[nodeid] for nodeid in sorted(self.durations_s)
            },
        }


def _build_pytest_args(repo_root: Path, extra_args: list[str], maxfail: int | None) -> list[str]:
    basetemp = Path("contract_gate_tmp") / "pytest-contract"
    cache_dir = basetemp / ".cache"
    basetemp.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    args = [
        "tests/contract",
        "-m",
        "contract",
        "-q",
        "--tb=short",
        f"--basetemp={basetemp}",
        "-o",
        f"cache_dir={cache_dir}",
    ]
    if maxfail is not None:
        args.append(f"--maxfail={maxfail}")
    args.extend(extra_args)
    return args


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the backend DS semantic contract gate.")
    parser.add_argument(
        "--maxfail",
        type=int,
        default=0,
        help="Stop after N failing tests. Use 0 to run the full contract suite.",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional pytest arguments. Prefix with -- to forward options.",
    )
    args = parser.parse_args()

    extra_args = list(args.pytest_args)
    if extra_args[:1] == ["--"]:
        extra_args = extra_args[1:]

    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)
    plugin = ContractReportPlugin()
    exit_code = pytest.main(
        _build_pytest_args(
            repo_root=repo_root,
            extra_args=extra_args,
            maxfail=args.maxfail or None,
        ),
        plugins=[plugin],
    )
    summary = plugin.build_summary(int(exit_code))
    print(f"DS_CONTRACT_STATUS={summary['status']}")
    print("DS_CONTRACT_SUMMARY=" + json.dumps(summary, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
