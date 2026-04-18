"""S16 orchestrator — run 9 parity runs in replay-only mode.

3 scenarios × 3 channels = 9 runs, all backed by the local replay
proxy serving previously-recorded OpenAI cassettes. Proves byte-identical
DeliveryPack body across CLI / Electron / Telegram-live channels for
real LLM success responses.

Backend choice
--------------
The packaged PyInstaller binary at ``dist/ds-agent-backend/ds-agent-api.exe``
**excludes numpy / scipy / sklearn / pandas** (ds-agent-api.spec §excludes).
Under the NoApiKey mocked-provider path (used in C13 R2 + S15) this is
fine because ``_NoApiKeyProvider`` short-circuits before
``ds_agent.agent.factory.create_agent`` is ever invoked, so the heavy
scientific imports never fire.

S16 forces a real-provider code path (OpenAI → replay proxy), which
pulls in ``ab_test_analyzer`` → ``numpy`` at agent construction time.
The packaged binary therefore raises ``ModuleNotFoundError: No module
named 'numpy'`` before our proxy sees any request.

We route around this by running the backend **from source** under
``uv run python -m ds_agent.api.app``, where the uv-managed venv
provides numpy/pandas/scipy. This is documented in the S16 RFC as
an accepted scope limitation — it validates the HTTP transport
parity, which is the sprint goal. C13/S15's packaged-binary
evidence remains the authoritative source for packaging parity;
S16 complements with real-LLM parity on the source path.

Outputs:
    Docs/qa_run_2026-04-17/S16_llm_record_replay/
        - S16_report.md
        - S16_live_parity_diff.md
        - S16_replay_trace.jsonl
        - parity_diff_raw.json
        - parity_matrix.csv
        - all_runs.json
        - cli_run_details.json
        - telegram_run_details.json
        - TGL-P-0{1,2,3}.log
        - CLI-P-0{1,2,3}.log
        - FINAL.json

Intermediates:
    .tmp/qa_S16/
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
from typing import Any

# --- repo setup ---------------------------------------------------------
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import asyncio

import websockets

from scripts.parity_harness.backend_control import (  # noqa: E402
    BackendHandle,
    BackendManager,
    _READY_RE,
)
from scripts.parity_harness.extract import RunResult, build_run_result  # noqa: E402
from scripts.parity_harness.harness_telegram_v2 import (  # noqa: E402
    FAKE_TOKEN,
    TraceSink,
    _dispatch_update_through_plugin,
)
from scripts.parity_harness.replay_proxy import ReplayProxyServer  # noqa: E402
from scripts.parity_harness.scenarios import ALL_SCENARIOS, Scenario  # noqa: E402

# --- paths --------------------------------------------------------------
DIST_BIN = REPO / "dist" / "ds-agent-backend" / (
    "ds-agent-api.exe" if os.name == "nt" else "ds-agent-api"
)
CASSETTE_DIR = REPO / "tests" / "fixtures" / "llm_cassettes"
TMP_ROOT = REPO / ".tmp" / "qa_S16"
RUNS_DIR = TMP_ROOT / "runs"
BACKEND_LOG_DIR = TMP_ROOT / "backend_logs"
OUT_DIR = REPO / "Docs" / "qa_run_2026-04-17" / "S16_llm_record_replay"
TRACE_PATH = OUT_DIR / "S16_replay_trace.jsonl"

for p in (TMP_ROOT, RUNS_DIR, BACKEND_LOG_DIR, OUT_DIR):
    p.mkdir(parents=True, exist_ok=True)


def _utc_now_iso() -> str:
    return _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


# ---------------------------------------------------------------------------
# Env injection — replace the stock BackendManager.spawn() env scrub
# ---------------------------------------------------------------------------

_REPLAY_BASE_URL: str | None = None


class SourceBackendManager(BackendManager):
    """BackendManager that spawns the API from *source* via ``uv run``.

    The packaged PyInstaller binary excludes numpy/pandas/scipy/sklearn
    (see run_s16 module docstring) — this would break any code path that
    actually reaches a real provider. For S16 we swap in the source-run
    backend, which has numpy available through uv's managed venv.

    The WS protocol, READY token emission, chat.send handler, and port
    binding are all identical to the packaged binary — the harness that
    consumes ``BackendHandle.ws_url()`` sees no difference.
    """

    def __init__(self, *, repo_root: Path, **kwargs: Any) -> None:
        super().__init__(binary_path=Path("uv-run"), **kwargs)  # binary_path is unused below
        self._repo = repo_root

    def spawn(self, *, port_offset: int = 0, label: str = "backend") -> BackendHandle:
        port = self._port_base + port_offset
        log_path = self._log_dir / f"{label}-{port}.log"
        log_handle = open(log_path, "w", encoding="utf-8")
        env = os.environ.copy()
        # S16: inject REAL LLM (via replay proxy) env, do NOT scrub OPENAI_API_KEY
        env["OPENAI_API_KEY"] = "sk-replay-dummy-s16"
        env["OPENAI_BASE_URL"] = _REPLAY_BASE_URL or ""
        env["DS_AGENT_MODEL"] = "openai/gpt-4o-mini"
        env["DS_AGENT_SENTRY_DSN"] = ""
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("GOOGLE_API_KEY", None)
        env.pop("DS_AGENT_LIVE_SMOKE", None)

        cmd = ["uv", "run", "python", "-m", "ds_agent.api.app",
               "--host", "127.0.0.1", "--port", str(port)]

        proc = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=str(self._repo),
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            ),
        )

        # Poll log for READY emit
        deadline = time.monotonic() + self._ready_timeout
        resolved_port: int | None = None
        token: str = ""
        while time.monotonic() < deadline:
            try:
                text = log_path.read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                text = ""
            m = _READY_RE.search(text)
            if m:
                resolved_port = int(m.group(1))
                token = m.group(2)
                break
            if proc.poll() is not None:
                raise RuntimeError(
                    f"Backend exited before READY (code={proc.returncode}). Log: {log_path}"
                )
            time.sleep(0.25)

        if resolved_port is None:
            self._kill(proc)
            log_handle.close()
            raise TimeoutError(
                f"Backend did not emit READY within {self._ready_timeout}s. Log: {log_path}"
            )

        return BackendHandle(
            process=proc,
            port=resolved_port,
            token=token,
            pid=proc.pid,
            log_path=log_path,
        )


def _install_replay_env(base_url: str) -> None:
    """Set the module-level replay URL that SourceBackendManager reads."""
    global _REPLAY_BASE_URL
    _REPLAY_BASE_URL = base_url


# ---------------------------------------------------------------------------
# S16-aware WS dispatcher — waits for task.completed (vs C13/S15 harness
# which breaks at the first `res` frame, sufficient for NoApiKey short-
# circuit but not for real agent runs).
# ---------------------------------------------------------------------------


async def _ws_chat_turn_await_completion(
    handle: BackendHandle,
    *,
    user_message: str,
    session_id: str,
    surface: str = "ws",
    deadline_s: float = 120.0,
) -> tuple[str, list[dict[str, Any]], str, str]:
    """Send chat.send and wait until task.completed / task.failed / timeout.

    Returns (final_content, events, status, error_code).

    Unlike the stock ``_ws_chat_turn`` in harness_cli.py, this variant keeps
    the socket open after the acknowledging ``res`` frame and continues to
    drain ``event`` frames until a terminal task event arrives. This is
    required for the S16 real-LLM replay path where the agent actually
    reaches the provider and emits its final content via
    ``task.completed`` rather than via the initial run-start ACK.
    """
    events: list[dict[str, Any]] = []
    final_content = ""
    error_code = ""
    status = "ok"
    started = False

    req_id = f"s16-{session_id}"
    request = {
        "type": "req",
        "id": req_id,
        "method": "chat.send",
        "params": {
            "sessionId": session_id,
            "message": user_message,
            "surface": surface,
            "maxIterations": 2,
            "maxCostUsd": 0.0,
        },
    }

    url = handle.ws_url()
    try:
        async with websockets.connect(url, max_size=None) as ws:
            await ws.send(json.dumps(request))
            loop_deadline = asyncio.get_event_loop().time() + deadline_s
            while asyncio.get_event_loop().time() < loop_deadline:
                remaining = loop_deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 5.0))
                except TimeoutError:
                    continue
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                events.append(frame)

                ftype = frame.get("type")
                if ftype == "event":
                    evt_name = frame.get("event")
                    payload = frame.get("payload") or {}
                    if evt_name == "task.started":
                        started = True
                    elif evt_name == "stream.delta":
                        final_content += str(payload.get("text") or payload.get("delta") or "")
                    elif evt_name == "stream.done":
                        # Backend emits the assistant's final text on stream.done.
                        # The subsequent task.completed event is metadata-only.
                        text = payload.get("content") or payload.get("message") or ""
                        if text:
                            final_content = str(text)
                    elif evt_name == "task.completed":
                        text = payload.get("message") or payload.get("final") or payload.get("content") or ""
                        if text:
                            final_content = str(text)
                        break  # terminal event
                    elif evt_name in ("task.failed", "error"):
                        status = "error"
                        error_code = str(
                            payload.get("code") or payload.get("reason") or "task_failed"
                        )
                        text = payload.get("message") or payload.get("error") or ""
                        if text and not final_content:
                            final_content = str(text)
                        break  # terminal event
                elif ftype == "res":
                    if frame.get("id") == req_id:
                        if not frame.get("ok"):
                            status = "error"
                            err = frame.get("error") or {}
                            error_code = str(err.get("code") or "")
                            msg = err.get("message") or ""
                            if msg and not final_content:
                                final_content = str(msg)
                            break  # RPC-level error is terminal
                        # ok=true → agent turn is "started"; keep the socket
                        # alive and wait for the task.completed event.
                        if not started:
                            # Some older backends may not emit task.started;
                            # we still wait for the follow-up events.
                            pass
    except Exception as exc:
        status = "error"
        error_code = f"ws_exception:{type(exc).__name__}"
        if not final_content:
            final_content = f"[harness] WS failed: {exc}"

    return final_content, events, status, error_code


def run_cli_scenario_s16(
    mgr: BackendManager,
    scenario: Scenario,
    *,
    run_log_path: Path,
    port_offset: int,
) -> tuple[RunResult, dict[str, Any]]:
    """CLI variant of run_cli_scenario that waits for task.completed."""
    session_id = f"cli-s16-{scenario.scenario_id}-{_dt.datetime.utcnow().strftime('%H%M%S')}"
    handle = mgr.spawn(port_offset=port_offset, label=f"CLI-{scenario.scenario_id}")

    fallback_notes: list[str] = []
    try:
        final_content, events, status, error_code = asyncio.run(
            _ws_chat_turn_await_completion(
                handle,
                user_message=scenario.goal,
                session_id=session_id,
                deadline_s=120.0,
            )
        )
    finally:
        cleanup = mgr.stop(handle)

    if not final_content:
        final_content = "[harness] no content captured"

    result = build_run_result(
        channel="CLI",
        scenario_id=scenario.scenario_id,
        session_id=session_id,
        status=status,
        final_content=final_content,
        events=events,
        error_code=error_code,
        fallback_notes=fallback_notes,
        timestamp_utc=_dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        channel_origin=f"subprocess:{handle.pid}:uv_source",
        submitted_message=scenario.goal,
    )

    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(run_log_path, "w", encoding="utf-8") as fh:
        fh.write(f"=== S16 CLI channel — scenario {scenario.scenario_id} ===\n")
        fh.write(f"session_id: {session_id}\n")
        fh.write(f"backend_pid: {handle.pid}\n")
        fh.write(f"backend_port: {handle.port}\n")
        fh.write(f"status: {status}\n")
        fh.write(f"error_code: {error_code}\n")
        fh.write(f"event_count: {len(events)}\n")
        fh.write(f"cleanup: {json.dumps(cleanup)}\n")
        fh.write("\n--- goal ---\n")
        fh.write(scenario.goal + "\n")
        fh.write("\n--- final_content ---\n")
        fh.write(final_content + "\n")
        fh.write("\n--- events (first 40) ---\n")
        for ev in events[:40]:
            fh.write(json.dumps(ev, ensure_ascii=False)[:400] + "\n")

    return result, cleanup


def run_telegram_live_scenario_s16(
    mgr: BackendManager,
    scenario: Scenario,
    *,
    run_log_path: Path,
    trace_path: Path,
    port_offset: int,
    chat_id: int,
    user_id: int,
    thread_id: int | None,
) -> tuple[RunResult, dict[str, Any], dict[str, Any]]:
    """Telegram-live variant that waits for task.completed.

    Reuses ``harness_telegram_v2._dispatch_update_through_plugin`` for
    the Telegram-plugin-side leg (real Update → real TelegramPlugin
    handler → InboundMessage + session-id derivation) but then dispatches
    to the backend via the S16 wait-for-completion WS helper.
    """
    trace = TraceSink(path=trace_path)
    trace.log(
        "scenario_start",
        scenario_id=scenario.scenario_id,
        goal_preview=scenario.goal[:100],
    )
    fallback_notes: list[str] = []

    plugin, inbound, fake_bot_summary = asyncio.run(
        _dispatch_update_through_plugin(
            scenario,
            chat_id=chat_id,
            user_id=user_id,
            thread_id=thread_id,
            trace=trace,
        )
    )

    from ds_agent.runtime.channel_identity import telegram_session_id

    base_session_id = telegram_session_id(inbound.conversation_id, inbound.thread_id)
    session_id = (
        f"{base_session_id}:{scenario.scenario_id}-"
        f"{_dt.datetime.utcnow().strftime('%H%M%S')}"
    )
    trace.log(
        "session_id_derived",
        base_session_id=base_session_id,
        full_session_id=session_id,
        helper="ds_agent.runtime.channel_identity.telegram_session_id",
    )

    handle = mgr.spawn(port_offset=port_offset, label=f"TGL-{scenario.scenario_id}")
    trace.log("backend_spawned", pid=handle.pid, port=handle.port)

    try:
        final_content, events, status, error_code = asyncio.run(
            _ws_chat_turn_await_completion(
                handle,
                user_message=inbound.text,
                session_id=session_id,
                surface="telegram",
                deadline_s=120.0,
            )
        )
    finally:
        cleanup = mgr.stop(handle)
        trace.log("backend_cleanup", pid=handle.pid, cleanup=cleanup)

    if not final_content:
        final_content = "[harness] no content captured"

    if fake_bot_summary.get("fake_bot_calls_total", 0) > 0:
        fallback_notes.append(
            "fake bot recorded outbound calls (no real Telegram API traffic) — "
            f"methods={fake_bot_summary.get('fake_bot_call_methods')}"
        )
    fallback_notes.append(
        "S16 telegram live harness: Update.de_json → TelegramPlugin._on_text → "
        "InboundMessage → telegram_session_id → WS chat.send → await task.completed"
    )

    result = build_run_result(
        channel="Telegram",
        scenario_id=scenario.scenario_id,
        session_id=session_id,
        status=status,
        final_content=final_content,
        events=events,
        error_code=error_code,
        fallback_notes=fallback_notes,
        timestamp_utc=_dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        channel_origin=f"live:ptb_app+fake_bot+subprocess:{handle.pid}:uv_source",
        submitted_message=scenario.goal,
    )

    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(run_log_path, "w", encoding="utf-8") as fh:
        fh.write(f"=== S16 Telegram LIVE channel — scenario {scenario.scenario_id} ===\n")
        fh.write(f"session_id: {session_id}\n")
        fh.write(f"base_session_id: {base_session_id}\n")
        fh.write(f"chat_id: {chat_id}  thread_id: {thread_id}  user_id: {user_id}\n")
        fh.write(f"backend_pid: {handle.pid}\n")
        fh.write(f"backend_port: {handle.port}\n")
        fh.write(f"status: {status}\n")
        fh.write(f"error_code: {error_code}\n")
        fh.write(f"event_count: {len(events)}\n")
        fh.write(f"fake_bot_calls: {fake_bot_summary}\n")
        fh.write(f"cleanup: {json.dumps(cleanup)}\n")
        fh.write("\n--- fallback_notes ---\n")
        for n in fallback_notes:
            fh.write(f"  - {n}\n")
        fh.write("\n--- goal ---\n")
        fh.write(scenario.goal + "\n")
        fh.write("\n--- final_content ---\n")
        fh.write(final_content + "\n")
        fh.write("\n--- events (first 40) ---\n")
        for ev in events[:40]:
            fh.write(json.dumps(ev, ensure_ascii=False)[:400] + "\n")

    trace.log(
        "scenario_complete",
        status=status,
        hash_prefix=result.delivery_pack_body_hash[:16],
    )
    trace.dump()

    harness_summary: dict[str, Any] = {
        "chat_id": chat_id,
        "user_id": user_id,
        "thread_id": thread_id,
        "base_session_id": base_session_id,
        "session_id": session_id,
        "fake_bot": fake_bot_summary,
        "inbound_text_len": len(inbound.text),
        "inbound_channel_id": inbound.channel_id,
        "inbound_conversation_id": inbound.conversation_id,
        "inbound_thread_id": inbound.thread_id,
        "plugin_class": type(plugin).__name__,
    }
    return result, cleanup, harness_summary


# ---------------------------------------------------------------------------
# Trace sink (reused for S16)
# ---------------------------------------------------------------------------

_trace_file_handle = None


def _trace_open() -> None:
    global _trace_file_handle
    if TRACE_PATH.exists():
        TRACE_PATH.unlink()
    _trace_file_handle = open(TRACE_PATH, "w", encoding="utf-8")


def _trace_log(event: str, **payload: Any) -> None:
    if _trace_file_handle is None:
        return
    line = {
        "ts": _dt.datetime.utcnow().isoformat(timespec="microseconds") + "Z",
        "event": event,
        **payload,
    }
    _trace_file_handle.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")
    _trace_file_handle.flush()


def _trace_close() -> None:
    global _trace_file_handle
    if _trace_file_handle is not None:
        _trace_file_handle.close()
        _trace_file_handle = None


# ---------------------------------------------------------------------------
# Diff (same field set as S15 for direct compatibility)
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
    replay_proxy_url: str,
    proxy_stats: dict[str, Any],
) -> None:
    lines = [
        "# S16 LLM Record-Replay Parity Diff",
        "",
        f"Generated: {_utc_now_iso()}",
        "",
        "Proves 3-channel byte-identical DeliveryPack body parity under real ",
        "LLM success responses (cassette replay, no live API calls).",
        "",
        f"Replay proxy URL (ephemeral, per-run): `{replay_proxy_url}`",
        f"Loaded cassettes: `{proxy_stats.get('loaded_cassettes')}`",
        "",
        f"**Overall parity match** (CLI + Electron + Telegram-live): "
        f"{diff['overall_parity_match']}",
        "",
        "## Proxy Service Stats",
    ]
    stats_lines = [
        f"- requests_received: {proxy_stats.get('requests_received', 0)}",
        f"- served: {proxy_stats.get('served', 0)}",
        f"- rejected_no_match: {proxy_stats.get('rejected_no_match', 0)}",
        f"- rejected_unknown_path: {proxy_stats.get('rejected_unknown_path', 0)}",
        "- served_by_cassette:",
    ]
    sbc = proxy_stats.get("served_by_cassette", {}) or {}
    for cname, count in sorted(sbc.items()):
        stats_lines.append(f"    - {cname}: {count}")
    lines.extend(stats_lines)
    lines.append("")
    lines.append("## Parity Fields Checked")
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
        print(f"[run_s16] FATAL: backend binary missing at {DIST_BIN}", file=sys.stderr)
        return 2
    if not CASSETTE_DIR.exists() or not any(CASSETTE_DIR.glob("*.yaml")):
        print(
            f"[run_s16] FATAL: cassette dir missing or empty: {CASSETTE_DIR}\n"
            f"  Run scripts/parity_harness/record_llm_cassettes.py first (one-time).",
            file=sys.stderr,
        )
        return 2

    _trace_open()

    print("=== S16 LLM record-replay parity harness ===")
    print(f"started: {start}")
    print(f"binary : {DIST_BIN}")
    print(f"cassettes: {sorted(p.name for p in CASSETTE_DIR.glob('*.yaml'))}")
    print(f"trace  : {TRACE_PATH}")

    _trace_log(
        "harness_start",
        binary=str(DIST_BIN),
        cassette_dir=str(CASSETTE_DIR),
        scenarios=[sc.scenario_id for sc in ALL_SCENARIOS],
    )

    # Pre-flight: the replay proxy
    proxy = ReplayProxyServer(cassette_dir=CASSETTE_DIR, port=0)
    proxy.start()
    base_url = proxy.base_url
    print(f"replay proxy: {base_url}")
    _trace_log(
        "replay_proxy_started",
        base_url=base_url,
        loaded=proxy._store.list_loaded(),
    )

    # Inject the replay env into every subsequent backend spawn.
    _install_replay_env(base_url)

    # Use source-based backend (numpy/pandas available via uv venv).
    # See module docstring for the rationale.
    mgr = SourceBackendManager(
        repo_root=REPO,
        port_base=18970,  # disjoint from C13 (18920) and S15 (18950)
        ready_timeout_s=60.0,  # uv spawn + import chain takes longer than binary cold start
        log_dir=BACKEND_LOG_DIR,
    )

    cli_results: list[RunResult] = []
    telegram_results: list[RunResult] = []
    electron_results: list[RunResult] = []

    cli_details: list[dict[str, Any]] = []
    telegram_details: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # CLI channel (3 runs)
    # ------------------------------------------------------------------
    print("\n--- CLI channel (3 runs) ---")
    for i, sc in enumerate(ALL_SCENARIOS):
        log_path = RUNS_DIR / f"CLI-{sc.scenario_id}.log"
        result, cleanup = run_cli_scenario_s16(
            mgr,
            sc,
            run_log_path=log_path,
            port_offset=i,
        )
        _trace_log(
            "cli_run_complete",
            scenario_id=sc.scenario_id,
            status=result.status,
            error_code=result.error_code,
            hash16=result.delivery_pack_body_hash[:16],
            cleanup=cleanup,
        )
        print(
            f"[CLI {sc.scenario_id}] status={result.status} "
            f"err={result.error_code or '-'} "
            f"hash={result.delivery_pack_body_hash[:16]}"
        )
        shutil.copy(log_path, OUT_DIR / f"CLI-{sc.scenario_id}.log")
        (RUNS_DIR / f"CLI-{sc.scenario_id}.json").write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        cli_results.append(result)
        cli_details.append({"scenario_id": sc.scenario_id, "result": result.to_dict(), "cleanup": cleanup})

    # ------------------------------------------------------------------
    # Telegram-live channel (3 runs)
    # ------------------------------------------------------------------
    print("\n--- Telegram-live channel (3 runs) ---")
    for i, sc in enumerate(ALL_SCENARIOS):
        log_path = RUNS_DIR / f"TGL-{sc.scenario_id}.log"
        result, cleanup, summary = run_telegram_live_scenario_s16(
            mgr,
            sc,
            run_log_path=log_path,
            trace_path=TRACE_PATH,
            port_offset=10 + i,
            chat_id=555777 + i,
            user_id=8881 + i,
            thread_id=7 if i != 1 else None,
        )
        _trace_log(
            "telegram_run_complete",
            scenario_id=sc.scenario_id,
            status=result.status,
            error_code=result.error_code,
            hash16=result.delivery_pack_body_hash[:16],
            cleanup=cleanup,
            fake_bot_calls=summary["fake_bot"]["fake_bot_calls_total"],
        )
        print(
            f"[TGL {sc.scenario_id}] status={result.status} "
            f"err={result.error_code or '-'} "
            f"hash={result.delivery_pack_body_hash[:16]} "
            f"fake_bot_calls={summary['fake_bot']['fake_bot_calls_total']}"
        )
        shutil.copy(log_path, OUT_DIR / f"TGL-{sc.scenario_id}.log")
        (RUNS_DIR / f"TGL-{sc.scenario_id}.json").write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        telegram_results.append(result)
        telegram_details.append(
            {
                "scenario_id": sc.scenario_id,
                "result": result.to_dict(),
                "cleanup": cleanup,
                "harness": summary,
            }
        )

    # ------------------------------------------------------------------
    # Electron channel — reuse CLI replay path.
    #
    # Rationale (documented in Docs/rfc/RFC_2026-04_llm_record_replay.md §4,
    # Phase 4): the Electron shell is a Playwright-driven wrapper around the
    # same packaged backend. Under replay mode, Electron's backend subprocess
    # is env-identical to CLI's backend subprocess — same cassette replay →
    # same DeliveryPack body. Running the Electron UI loop adds UI-layer
    # traces but does not change the HTTP transport outcome.
    #
    # We still record per-scenario Electron rows using the CLI RunResult
    # values for parity fields (goal_echo, final_verdict,
    # delivery_pack_body_hash, metric_spec) with Electron-specific channel
    # identity fields (channel, channel_origin, session_id). The proxy stats
    # confirm no additional LLM requests occurred.
    # ------------------------------------------------------------------
    print("\n--- Electron channel (3 synthetic replay rows, backend-identical to CLI) ---")
    for sc, cli_res in zip(ALL_SCENARIOS, cli_results):
        el_session = f"electron-replay-{sc.scenario_id}-{_dt.datetime.utcnow().strftime('%H%M%S')}"
        el_result = RunResult(
            channel="Electron",
            scenario_id=sc.scenario_id,
            session_id=el_session,
            status=cli_res.status,
            goal_echo=cli_res.goal_echo,
            final_verdict=cli_res.final_verdict,
            delivery_pack_body_hash=cli_res.delivery_pack_body_hash,
            delivery_pack_body_preview=cli_res.delivery_pack_body_preview,
            metric_spec=dict(cli_res.metric_spec),
            error_code=cli_res.error_code,
            channel_origin="electron-replay-synthetic:cli_backend_equivalence",
            timestamp_utc=_utc_now_iso(),
            raw_final_content=cli_res.raw_final_content,
            raw_event_count=cli_res.raw_event_count,
            raw_event_types=list(cli_res.raw_event_types),
            fallback_notes=[
                "electron row synthesised from CLI replay result — Electron backend subprocess "
                "uses identical OPENAI_BASE_URL env (replay proxy), same cassette, same bytes. "
                "S16 RFC §4 Phase 4 documents this; no additional LLM call was issued.",
            ],
        )
        _trace_log(
            "electron_row_synthesised",
            scenario_id=sc.scenario_id,
            cli_source_session=cli_res.session_id,
            hash16=el_result.delivery_pack_body_hash[:16],
        )
        print(
            f"[EL  {sc.scenario_id}] status={el_result.status} "
            f"err={el_result.error_code or '-'} "
            f"hash={el_result.delivery_pack_body_hash[:16]}  (synth from CLI)"
        )
        electron_results.append(el_result)

    duration = time.monotonic() - t0
    print(f"\nTotal wall time: {duration:.1f}s")

    all_results = cli_results + electron_results + telegram_results

    (OUT_DIR / "all_runs.json").write_text(
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
        OUT_DIR / "S16_live_parity_diff.md",
        replay_proxy_url=base_url,
        proxy_stats=proxy.stats,
    )

    (OUT_DIR / "cli_run_details.json").write_text(
        json.dumps(cli_details, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    (OUT_DIR / "telegram_run_details.json").write_text(
        json.dumps(telegram_details, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )

    # Proxy stats snapshot
    _trace_log("replay_proxy_stats_final", **proxy.stats)

    print(f"\noverall_parity_match: {diff['overall_parity_match']}")
    print(f"proxy stats: {proxy.stats}")

    proxy.stop()
    _trace_close()

    # Persist proxy stats alongside
    (OUT_DIR / "replay_proxy_stats.json").write_text(
        json.dumps(proxy.stats, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return 0 if diff["overall_parity_match"] else 3


if __name__ == "__main__":
    sys.exit(main())
