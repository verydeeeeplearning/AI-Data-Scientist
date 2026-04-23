"""S15 orchestrator — run 3 Telegram-LIVE scenarios via fake bot harness.

Reuses C13 Round 2 CLI + Electron results from
``Docs/qa_run_2026-04-17/C13_parity_process_level/all_runs.json``.

Outputs go to
``Docs/qa_run_2026-04-17/S15_telegram_live_parity/`` with intermediates in
``.tmp/qa_S15/``.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import os
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

# --- repo root setup --------------------------------------------------------
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.parity_harness.backend_control import BackendManager
from scripts.parity_harness.extract import RunResult
from scripts.parity_harness.harness_telegram_v2 import (
    run_telegram_live_scenario,
)
from scripts.parity_harness.scenarios import ALL_SCENARIOS

# --- paths ------------------------------------------------------------------
DIST_BIN = REPO / "dist" / "ds-agent-backend" / (
    "ds-agent-api.exe" if os.name == "nt" else "ds-agent-api"
)
TMP_ROOT = REPO / ".tmp" / "qa_S15"
RUNS_DIR = TMP_ROOT / "runs"
OUT_DIR = REPO / "Docs" / "qa_run_2026-04-17" / "S15_telegram_live_parity"
PRIOR_C13_DIR = REPO / "Docs" / "qa_run_2026-04-17" / "C13_parity_process_level"

TMP_ROOT.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRACE_PATH = OUT_DIR / "S15_telegram_fake_harness_trace.jsonl"


def _utc_now_iso() -> str:
    return _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


# ---------------------------------------------------------------------------
# Prior-result loader
# ---------------------------------------------------------------------------


def load_round2_results() -> list[RunResult]:
    """Load CLI + Electron runs from the C13 Round 2 corpus (fresh reload)."""
    raw_path = PRIOR_C13_DIR / "all_runs.json"
    if not raw_path.exists():
        raise FileNotFoundError(
            f"Round 2 corpus missing: {raw_path} — cannot compute parity"
        )
    rows = json.loads(raw_path.read_text(encoding="utf-8"))
    results: list[RunResult] = []
    for row in rows:
        if row.get("channel") not in {"CLI", "Electron"}:
            # Drop the old Telegram-shaped-id fallback runs; S15 replaces them.
            continue
        results.append(
            RunResult(
                channel=row["channel"],
                scenario_id=row["scenario_id"],
                session_id=row.get("session_id", ""),
                status=row.get("status", "error"),
                goal_echo=row.get("goal_echo", ""),
                final_verdict=row.get("final_verdict", ""),
                delivery_pack_body_hash=row.get("delivery_pack_body_hash", ""),
                delivery_pack_body_preview=row.get("delivery_pack_body_preview", ""),
                metric_spec=row.get("metric_spec", {}),
                error_code=row.get("error_code", ""),
                channel_origin=row.get("channel_origin", ""),
                timestamp_utc=row.get("timestamp_utc", ""),
                raw_final_content=row.get("raw_final_content", ""),
                raw_event_count=row.get("raw_event_count", 0),
                raw_event_types=row.get("raw_event_types", []),
                fallback_notes=row.get("fallback_notes", []),
            )
        )
    return results


# ---------------------------------------------------------------------------
# Diff (reuses the same fields + semantics as run_all.py)
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
    "status",
    "error_code",
}

_PARITY_FIELDS = [
    "goal_echo",
    "final_verdict",
    "delivery_pack_body_hash",
    "metric_spec",
]


def compare_runs(results: list[RunResult]) -> dict[str, Any]:
    by_scenario: dict[str, list[RunResult]] = {}
    for r in results:
        by_scenario.setdefault(r.scenario_id, []).append(r)

    overall_match = True
    per_scenario: dict[str, Any] = {}
    for sid, rs in by_scenario.items():
        channel_values: dict[str, dict[str, Any]] = {r.channel: r.to_dict() for r in rs}
        mismatches: list[dict[str, Any]] = []
        for field in _PARITY_FIELDS:
            vals = {ch: v.get(field) for ch, v in channel_values.items()}
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


def write_diff_md(
    results: list[RunResult],
    diff: dict[str, Any],
    path: Path,
    *,
    round2_source: str,
) -> None:
    lines = [
        "# S15 Telegram LIVE Parity Diff",
        "",
        f"Generated: {_utc_now_iso()}",
        "",
        f"Round 2 CLI+Electron source: `{round2_source}`",
        "",
        f"**Overall parity match** (CLI + Electron + Telegram-live): "
        f"{diff['overall_parity_match']}",
        "",
        "## Parity Fields Checked",
    ]
    for f in diff["parity_fields_checked"]:
        lines.append(f"- `{f}`")
    lines.append("")
    lines.append("## Infra Fields Ignored (allowed to differ)")
    for f in diff["infra_fields_ignored"]:
        lines.append(f"- `{f}`")
    lines.append("")
    lines.append("## Per-Scenario Results (3 channels × 3 scenarios)")
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

    if not DIST_BIN.exists():
        print(f"[run_s15] FATAL: backend binary missing at {DIST_BIN}", file=sys.stderr)
        return 2

    # Ensure trace file is fresh this run (v2 harness appends)
    if TRACE_PATH.exists():
        TRACE_PATH.unlink()

    print("=== S15 Telegram LIVE parity harness ===")
    print(f"started: {start}")
    print(f"binary : {DIST_BIN}")
    print(f"trace  : {TRACE_PATH}")

    # Re-load Round 2 CLI + Electron results
    prior = load_round2_results()
    print(f"\nLoaded Round 2 CLI+Electron runs: {len(prior)}")

    mgr = BackendManager(
        binary_path=DIST_BIN,
        port_base=18950,  # disjoint from run_all.py (which used 18920)
        ready_timeout_s=30.0,
        log_dir=TMP_ROOT / "backend_logs",
    )

    # Run 3 Telegram LIVE scenarios
    live_results: list[RunResult] = []
    harness_summaries: list[dict[str, Any]] = []
    total_fake_bot_calls = 0
    real_tg_api_calls = 0  # always 0 by construction; surfaced for evidence
    scenario_run_details: list[dict[str, Any]] = []

    print("\n--- Telegram LIVE channel (3 runs) ---")
    for i, sc in enumerate(ALL_SCENARIOS):
        log_path = RUNS_DIR / f"TGL-{sc.scenario_id}.log"
        result, cleanup, summary = run_telegram_live_scenario(
            mgr,
            sc,
            run_log_path=log_path,
            trace_path=TRACE_PATH,
            port_offset=i,
            chat_id=555777 + i,  # distinct chat per scenario
            user_id=8881 + i,
            thread_id=7 if i != 1 else None,  # P-02 runs without thread
        )
        print(
            f"[TGL {sc.scenario_id}] status={result.status} "
            f"err={result.error_code or '-'} "
            f"hash={result.delivery_pack_body_hash[:16]} "
            f"fake_bot_calls={summary['fake_bot']['fake_bot_calls_total']}"
        )
        # Copy log to publish dir
        shutil.copy(log_path, OUT_DIR / f"TGL-{sc.scenario_id}.log")
        # Save JSON
        (RUNS_DIR / f"TGL-{sc.scenario_id}.json").write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        live_results.append(result)
        harness_summaries.append(summary)
        total_fake_bot_calls += summary["fake_bot"]["fake_bot_calls_total"]
        scenario_run_details.append(
            {
                "scenario_id": sc.scenario_id,
                "result": result.to_dict(),
                "cleanup": cleanup,
                "harness": summary,
            }
        )

    duration = time.monotonic() - t0
    print(f"\nTotal wall time: {duration:.1f}s")

    # Consolidate
    all_results = prior + live_results
    (OUT_DIR / "all_runs_including_live.json").write_text(
        json.dumps([asdict(r) for r in all_results], indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )

    diff = compare_runs(all_results)
    (OUT_DIR / "parity_diff_raw.json").write_text(
        json.dumps(diff, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    write_matrix_csv(all_results, OUT_DIR / "parity_matrix.csv")
    write_diff_md(
        all_results,
        diff,
        OUT_DIR / "S15_telegram_live_diff.md",
        round2_source=str(PRIOR_C13_DIR / "all_runs.json"),
    )

    # Dump the per-scenario harness detail JSON (evidence bundle)
    (OUT_DIR / "telegram_live_run_details.json").write_text(
        json.dumps(scenario_run_details, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )

    # Quick summary
    print(f"\noverall_parity_match: {diff['overall_parity_match']}")
    print(f"scenarios: {len(diff['scenarios'])}")
    print(f"total_fake_bot_calls: {total_fake_bot_calls}")
    print(f"real_telegram_api_calls: {real_tg_api_calls}")
    print(f"telegram live runs completed: {len(live_results)}")

    return 0 if diff["overall_parity_match"] else 3


if __name__ == "__main__":
    sys.exit(main())
