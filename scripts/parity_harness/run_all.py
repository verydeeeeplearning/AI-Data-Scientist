"""Phase 3 orchestrator — run 9 (3 scenarios × 3 channels) parity runs.

Writes per-run JSON + log files to ``.tmp/qa_phase3/runs/`` and publishes
the consolidated diff report + matrix to
``Docs/qa_run_2026-04-17/C13_parity_process_level/``.

Run:
    .venv/Scripts/python.exe scripts/parity_harness/run_all.py
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

# --- repo root setup --------------------------------------------------------
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.parity_harness.backend_control import BackendManager  # noqa: E402
from scripts.parity_harness.extract import RunResult, build_run_result  # noqa: E402
from scripts.parity_harness.harness_cli import run_cli_scenario  # noqa: E402
from scripts.parity_harness.harness_telegram import run_telegram_scenario  # noqa: E402
from scripts.parity_harness.scenarios import ALL_SCENARIOS  # noqa: E402

# --- paths ------------------------------------------------------------------
DIST_BIN = REPO / "dist" / "ds-agent-backend" / (
    "ds-agent-api.exe" if os.name == "nt" else "ds-agent-api"
)
ELECTRON_DIR = REPO / "electron"
ELECTRON_MAIN = ELECTRON_DIR / "dist" / "main" / "index.js"
TMP_ROOT = REPO / ".tmp" / "qa_phase3"
RUNS_DIR = TMP_ROOT / "runs"
OUT_DIR = REPO / "Docs" / "qa_run_2026-04-17" / "C13_parity_process_level"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)
TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _utc_now_iso() -> str:
    return _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


# ---------------------------------------------------------------------------
# Channel runners
# ---------------------------------------------------------------------------


def run_cli_channel(mgr: BackendManager) -> list[RunResult]:
    results: list[RunResult] = []
    cleanups: list[dict] = []
    for i, sc in enumerate(ALL_SCENARIOS):
        log_path = RUNS_DIR / f"CLI-{sc.scenario_id}.log"
        result, cleanup = run_cli_scenario(
            mgr, sc, run_log_path=log_path, port_offset=i
        )
        print(
            f"[CLI {sc.scenario_id}] status={result.status} "
            f"err={result.error_code or '-'} "
            f"hash={result.delivery_pack_body_hash[:16]}"
        )
        json_path = RUNS_DIR / f"CLI-{sc.scenario_id}.json"
        json_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        shutil.copy(log_path, OUT_DIR / f"CLI-{sc.scenario_id}.log")
        cleanups.append(cleanup)
        results.append(result)
    return results


def run_telegram_channel(mgr: BackendManager) -> list[RunResult]:
    results: list[RunResult] = []
    for i, sc in enumerate(ALL_SCENARIOS):
        log_path = RUNS_DIR / f"TG-{sc.scenario_id}.log"
        result, _ = run_telegram_scenario(
            mgr, sc, run_log_path=log_path, port_offset=10 + i
        )
        print(
            f"[TG  {sc.scenario_id}] status={result.status} "
            f"err={result.error_code or '-'} "
            f"hash={result.delivery_pack_body_hash[:16]}"
        )
        json_path = RUNS_DIR / f"TG-{sc.scenario_id}.json"
        json_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        shutil.copy(log_path, OUT_DIR / f"TG-{sc.scenario_id}.log")
        results.append(result)
    return results


def run_electron_channel() -> list[RunResult]:
    """Run the Node-based Playwright harness and parse its JSON outputs."""
    results: list[RunResult] = []
    fallback_global: list[str] = []

    if not ELECTRON_MAIN.exists():
        fallback_global.append(
            f"electron/dist/main/index.js missing at {ELECTRON_MAIN} — "
            "skipping live launch, will emit 'env-skip' placeholders"
        )
        node_ok = False
    else:
        node_ok = True

    # Attempt to run the Node harness.
    exec_status = "skipped"
    node_stdout = ""
    node_stderr = ""
    if node_ok:
        harness_js = REPO / "scripts" / "parity_harness" / "harness_electron.js"
        cmd = ["node", str(harness_js)]
        env = os.environ.copy()
        env["DS_AGENT_SENTRY_DSN"] = ""
        # The node harness itself has a hard timeout — put an outer one too.
        try:
            cp = subprocess.run(
                cmd,
                cwd=str(ELECTRON_DIR),
                env=env,
                capture_output=True,
                timeout=600,  # 10 min hard cap total
            )
            # Decode tolerantly — Windows can mix UTF-8 and cp949.
            node_stdout = (cp.stdout or b"").decode("utf-8", errors="replace")
            node_stderr = (cp.stderr or b"").decode("utf-8", errors="replace")
            exec_status = "ok" if cp.returncode == 0 else f"exit_{cp.returncode}"
        except subprocess.TimeoutExpired as exc:
            exec_status = "timeout"
            node_stderr = f"timeout: {exc}"
        except FileNotFoundError:
            exec_status = "node_not_found"
            fallback_global.append("node not on PATH")

    exec_log = RUNS_DIR / "EL-node-stdout.log"
    exec_log.write_text(
        (node_stdout or "") + "\n---STDERR---\n" + (node_stderr or ""),
        encoding="utf-8",
    )

    # Consume per-scenario JSON files written by the node harness.
    for i, sc in enumerate(ALL_SCENARIOS):
        el_json = RUNS_DIR / f"EL-{sc.scenario_id}.json"
        fallback_notes: list[str] = list(fallback_global)
        print(
            f"[EL  {sc.scenario_id}] loading harness output (exec_status={exec_status})"
        )
        if not el_json.exists():
            fallback_notes.append(
                "Electron harness did not produce a JSON output — treated as env-skip"
            )
            result = build_run_result(
                channel="Electron",
                scenario_id=sc.scenario_id,
                session_id=f"electron-skip-{sc.scenario_id}-{i}",
                status="error",
                final_content="[harness] electron output missing",
                events=[],
                error_code="ELECTRON_OUTPUT_MISSING",
                fallback_notes=fallback_notes,
                timestamp_utc=_utc_now_iso(),
                channel_origin=f"electron-env-skip ({exec_status})",
            )
        else:
            raw = json.loads(el_json.read_text(encoding="utf-8"))
            # Reconstruct RunResult directly from node output.
            result = RunResult(
                channel="Electron",
                scenario_id=raw.get("scenario_id", sc.scenario_id),
                session_id=raw.get("session_id", ""),
                status=raw.get("status", "error"),
                goal_echo=raw.get("goal_echo", ""),
                final_verdict=raw.get("final_verdict", ""),
                delivery_pack_body_hash=raw.get("delivery_pack_body_hash", ""),
                delivery_pack_body_preview=raw.get("delivery_pack_body_preview", ""),
                metric_spec=raw.get("metric_spec", {}),
                error_code=raw.get("error_code", ""),
                channel_origin=raw.get("channel_origin", ""),
                timestamp_utc=raw.get("timestamp_utc", _utc_now_iso()),
                raw_final_content=raw.get("raw_final_content", ""),
                raw_event_count=raw.get("raw_event_count", 0),
                raw_event_types=raw.get("raw_event_types", []),
                fallback_notes=raw.get("fallback_notes", []) + fallback_notes,
            )
        # Publish log if it exists
        log_path = RUNS_DIR / f"EL-{sc.scenario_id}.log"
        if log_path.exists():
            shutil.copy(log_path, OUT_DIR / f"EL-{sc.scenario_id}.log")
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Diff + matrix
# ---------------------------------------------------------------------------

_INFRA_FIELDS = {
    "channel",
    "channel_origin",
    "timestamp_utc",
    "session_id",
    "raw_final_content",
    "raw_event_count",
    "raw_event_types",
    "fallback_notes",
    "status",        # status depends on channel-specific bridge; not a parity field
    "error_code",    # same — surface-specific mapping is infra
}

_PARITY_FIELDS = [
    "goal_echo",
    "final_verdict",
    "delivery_pack_body_hash",
    "metric_spec",
]


def compare_runs(results: list[RunResult]) -> dict:
    """Build a scenario → match? report."""
    by_scenario: dict[str, list[RunResult]] = {}
    for r in results:
        by_scenario.setdefault(r.scenario_id, []).append(r)

    overall_match = True
    per_scenario: dict[str, dict] = {}
    for sid, rs in by_scenario.items():
        # Compare each parity field across channels
        channel_values: dict[str, dict] = {r.channel: r.to_dict() for r in rs}
        mismatches: list[dict] = []
        for field in _PARITY_FIELDS:
            vals = {ch: v.get(field) for ch, v in channel_values.items()}
            # All values equal?
            unique_vals = {json.dumps(v, sort_keys=True, default=str) for v in vals.values()}
            if len(unique_vals) > 1:
                mismatches.append({"field": field, "values": vals})
        match = len(mismatches) == 0
        if not match:
            overall_match = False
        per_scenario[sid] = {
            "match": match,
            "mismatches": mismatches,
            "channels_present": sorted(channel_values.keys()),
        }
    return {
        "overall_parity_match": overall_match,
        "scenarios": per_scenario,
        "parity_fields_checked": _PARITY_FIELDS,
        "infra_fields_ignored": sorted(_INFRA_FIELDS),
    }


def write_matrix_csv(results: list[RunResult], path: Path) -> None:
    cols = [
        "scenario_id",
        "channel",
        "status",
        "error_code",
        "delivery_pack_body_hash",
        "final_verdict",
        "channel_origin",
        "raw_event_count",
        "fallback",
    ]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(cols)
        for r in sorted(results, key=lambda x: (x.scenario_id, x.channel)):
            writer.writerow(
                [
                    r.scenario_id,
                    r.channel,
                    r.status,
                    r.error_code,
                    r.delivery_pack_body_hash[:16],
                    r.final_verdict,
                    r.channel_origin,
                    r.raw_event_count,
                    "; ".join(r.fallback_notes)[:200],
                ]
            )


def write_diff_md(results: list[RunResult], diff: dict, path: Path) -> None:
    lines = []
    lines.append("# C13 Parity Live Diff — Phase 3 Process-Level")
    lines.append("")
    lines.append(f"Generated: {_utc_now_iso()}")
    lines.append("")
    lines.append(f"**Overall parity match**: {diff['overall_parity_match']}")
    lines.append("")
    lines.append("## Parity Fields Checked")
    for f in diff["parity_fields_checked"]:
        lines.append(f"- `{f}`")
    lines.append("")
    lines.append("## Infra Fields Ignored (allowed to differ)")
    for f in diff["infra_fields_ignored"]:
        lines.append(f"- `{f}`")
    lines.append("")
    lines.append("## Per-Scenario Results")
    for sid, s in diff["scenarios"].items():
        lines.append(f"### Scenario {sid}")
        lines.append(f"- channels_present: {s['channels_present']}")
        lines.append(f"- match: **{s['match']}**")
        if not s["match"]:
            lines.append("")
            lines.append("#### Mismatches")
            for m in s["mismatches"]:
                lines.append(f"- **{m['field']}**")
                for ch, v in m["values"].items():
                    preview = json.dumps(v, default=str)[:120]
                    lines.append(f"  - {ch}: `{preview}`")
        lines.append("")

    lines.append("## Raw Results (per run)")
    for r in sorted(results, key=lambda x: (x.scenario_id, x.channel)):
        lines.append(f"### {r.channel} × {r.scenario_id}")
        lines.append(f"- status: `{r.status}`")
        lines.append(f"- error_code: `{r.error_code}`")
        lines.append(f"- session_id: `{r.session_id}`")
        lines.append(f"- channel_origin: `{r.channel_origin}`")
        lines.append(f"- delivery_pack_body_hash: `{r.delivery_pack_body_hash[:32]}…`")
        lines.append(f"- delivery_pack_body_preview: `{r.delivery_pack_body_preview[:140]}`")
        lines.append(f"- raw_event_count: {r.raw_event_count}")
        if r.fallback_notes:
            lines.append("- fallback_notes:")
            for n in r.fallback_notes:
                lines.append(f"  - {n}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    start = _utc_now_iso()
    t0 = time.monotonic()

    # Pre-flight checks
    if not DIST_BIN.exists():
        print(f"[run_all] FATAL: backend binary missing at {DIST_BIN}", file=sys.stderr)
        return 2

    mgr = BackendManager(
        binary_path=DIST_BIN,
        port_base=18920,
        ready_timeout_s=30.0,
        log_dir=TMP_ROOT / "backend_logs",
    )

    print("=== C13 Phase 3 parity harness ===")
    print(f"started: {start}")
    print(f"binary : {DIST_BIN}")

    results: list[RunResult] = []

    print("\n--- CLI channel (3 runs) ---")
    results.extend(run_cli_channel(mgr))

    print("\n--- Telegram channel (3 runs) ---")
    results.extend(run_telegram_channel(mgr))

    print("\n--- Electron channel (3 runs) ---")
    results.extend(run_electron_channel())

    duration = time.monotonic() - t0
    print(f"\nTotal wall time: {duration:.1f}s")

    # Consolidate
    all_json = [asdict(r) for r in results]
    (OUT_DIR / "all_runs.json").write_text(
        json.dumps(all_json, indent=2, default=str), encoding="utf-8"
    )

    diff = compare_runs(results)
    (OUT_DIR / "parity_diff_raw.json").write_text(
        json.dumps(diff, indent=2, default=str), encoding="utf-8"
    )
    write_matrix_csv(results, OUT_DIR / "parity_matrix.csv")
    write_diff_md(results, diff, OUT_DIR / "C13_parity_live_diff.md")

    # Quick summary
    print(f"\noverall_parity_match: {diff['overall_parity_match']}")
    print(f"runs_completed: {len(results)} / 9")
    print(f"CLI runs_ok     : {sum(1 for r in results if r.channel == 'CLI' and r.status == 'ok')}")
    print(f"CLI runs_err    : {sum(1 for r in results if r.channel == 'CLI' and r.status == 'error')}")
    print(f"Telegram ok     : {sum(1 for r in results if r.channel == 'Telegram' and r.status == 'ok')}")
    print(f"Telegram err    : {sum(1 for r in results if r.channel == 'Telegram' and r.status == 'error')}")
    print(f"Electron ok     : {sum(1 for r in results if r.channel == 'Electron' and r.status == 'ok')}")
    print(f"Electron err    : {sum(1 for r in results if r.channel == 'Electron' and r.status == 'error')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
