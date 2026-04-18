"""CLI channel harness — subprocess-level.

Spawns the bundled ``ds-agent-api.exe`` and drives it via the WebSocket
RPC protocol that the CLI (and Electron) both use to reach the
in-process ``DSAgent``. Mocked provider path = no API key, which routes
the CLI's ``_create_provider`` through ``_NoApiKeyProvider`` inside the
packaged binary (same code path both surfaces use).

This is "process-level CLI" per plan §6.1: the binary is a separate
process, I/O crosses stdio+TCP, and the subprocess cleanup is asserted.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import websockets

from scripts.parity_harness.backend_control import BackendHandle, BackendManager
from scripts.parity_harness.extract import RunResult, build_run_result
from scripts.parity_harness.scenarios import Scenario

logger = logging.getLogger(__name__)


async def _ws_chat_turn(
    handle: BackendHandle,
    *,
    user_message: str,
    session_id: str,
    deadline_s: float = 30.0,
) -> tuple[str, list[dict], str, str]:
    """Send one chat.send request. Returns (final_content, events, status, error_code)."""
    events: list[dict] = []
    final_content = ""
    error_code = ""
    status = "ok"

    req_id = f"c13p3-{session_id}"
    request = {
        "type": "req",
        "id": req_id,
        "method": "chat.send",
        "params": {
            "sessionId": session_id,
            "message": user_message,
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
                    if evt_name == "stream.delta":
                        delta = str(payload.get("text") or payload.get("delta") or "")
                        final_content += delta
                    elif evt_name == "task.completed":
                        # agent.run returned — harvest final text
                        text = payload.get("message") or payload.get("final") or ""
                        if text:
                            final_content = str(text)
                    elif evt_name in ("task.failed", "error"):
                        status = "error"
                        error_code = str(
                            payload.get("code")
                            or payload.get("reason")
                            or "task_failed"
                        )
                elif ftype == "res":
                    if frame.get("id") == req_id:
                        if not frame.get("ok"):
                            status = "error"
                            err = frame.get("error") or {}
                            error_code = str(err.get("code") or "")
                            # Error result content may carry an explanation
                            payload = frame.get("payload") or err
                            if isinstance(payload, dict):
                                msg = payload.get("message") or payload.get("detail") or ""
                                if msg and not final_content:
                                    final_content = str(msg)
                        else:
                            payload = frame.get("payload") or {}
                            text = payload.get("content") or payload.get("message") or ""
                            if text and not final_content:
                                final_content = str(text)
                        break  # Terminal frame
    except Exception as exc:
        status = "error"
        error_code = f"ws_exception:{type(exc).__name__}"
        if not final_content:
            final_content = f"[harness] WS connect/receive failed: {exc}"

    return final_content, events, status, error_code


def run_cli_scenario(
    backend_manager: BackendManager,
    scenario: Scenario,
    *,
    run_log_path: Path,
    port_offset: int = 0,
) -> tuple[RunResult, dict]:
    """Run one scenario through the CLI-shaped code path.

    Returns (RunResult, cleanup_info).
    """
    session_id = f"cli-{scenario.scenario_id}-{_dt.datetime.utcnow().strftime('%H%M%S')}"
    fallback_notes: list[str] = []

    # Spawn backend per-scenario for isolation.
    handle = backend_manager.spawn(port_offset=port_offset, label=f"CLI-{scenario.scenario_id}")

    try:
        final_content, events, status, error_code = asyncio.run(
            _ws_chat_turn(
                handle,
                user_message=scenario.goal,
                session_id=session_id,
                deadline_s=45.0,
            )
        )
    finally:
        cleanup = backend_manager.stop(handle)

    if not final_content:
        final_content = "[harness] no content captured"
    if error_code.startswith("task_failed") or error_code == "MISSING_PROVIDER":
        fallback_notes.append(
            "backend returned task_failed — expected under 'no API key' mocked provider path"
        )

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
        channel_origin=f"subprocess:{handle.pid}",
        submitted_message=scenario.goal,
    )

    # Persist run log
    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(run_log_path, "w", encoding="utf-8") as fh:
        fh.write(f"=== C13 Phase 3 CLI channel — scenario {scenario.scenario_id} ===\n")
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
            fh.write(json.dumps(ev)[:400] + "\n")

    return result, cleanup
