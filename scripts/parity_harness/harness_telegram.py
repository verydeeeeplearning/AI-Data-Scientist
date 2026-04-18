"""Telegram channel harness — fake-update path.

The ``TelegramRunner`` internally creates its DSAgent via
``create_agent`` with a ``TelegramCallbacks`` collaborator. In true
process-level parity we would spin up the Telegram daemon (``ds-agent
daemon``) and drive a fake Updater via python-telegram-bot's own test
harness.

**Environment reality (2026-04-17 QA venv)**: python-telegram-bot is
**not installed** (neither in ``.venv`` nor bundled inside
``dist/ds-agent-backend/_internal``). Installing it would require
network + exceeds Phase 3 scope ("source 수정 금지" + "real external 금지"
implies: harness only, no production dep churn).

**Adopted approach — true-to-spec-where-possible fallback**:

  1. Spawn the same packaged ``ds-agent-api.exe`` backend as the CLI
     harness (IDENTICAL factory path — the Telegram runner and the WS
     handler both invoke the same ``create_agent`` inside the binary).
  2. Open a WebSocket to the backend **carrying a Telegram-shaped
     session id** (``telegram:{chat_id}:{thread_id}``) to exercise the
     ``parse_telegram_session_id`` runtime hook that Telegram-origin
     messages take.
  3. Submit a ``chat.send`` whose ``params.surface`` is declared as
     ``telegram`` so the runtime event log records it as Telegram origin.

This is documented as a **fallback** in the Phase 3 report because the
fake-update leg of the Round 1 residual gap is still open: real
``python-telegram-bot`` polling → InboundMessage dispatch is not
exercised. The factory wiring parity (which is the only parity that C13
measures) IS exercised through the same binary with a Telegram-shaped
session identifier.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import logging
from pathlib import Path

import websockets

from scripts.parity_harness.backend_control import BackendHandle, BackendManager
from scripts.parity_harness.extract import RunResult, build_run_result
from scripts.parity_harness.scenarios import Scenario

logger = logging.getLogger(__name__)


async def _telegram_ws_turn(
    handle: BackendHandle,
    *,
    user_message: str,
    session_id: str,
    deadline_s: float = 30.0,
) -> tuple[str, list[dict], str, str]:
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
            "sessionId": session_id,  # Telegram-shaped id
            "message": user_message,
            "surface": "telegram",  # runtime event log marks origin
            "maxIterations": 2,
            "maxCostUsd": 0.0,
        },
    }

    try:
        async with websockets.connect(handle.ws_url(), max_size=None) as ws:
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
                        final_content += str(payload.get("text") or payload.get("delta") or "")
                    elif evt_name == "task.completed":
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
                            if isinstance(err, dict):
                                msg = err.get("message") or ""
                                if msg and not final_content:
                                    final_content = str(msg)
                        else:
                            payload = frame.get("payload") or {}
                            text = payload.get("content") or payload.get("message") or ""
                            if text and not final_content:
                                final_content = str(text)
                        break
    except Exception as exc:
        status = "error"
        error_code = f"ws_exception:{type(exc).__name__}"
        if not final_content:
            final_content = f"[harness] WS failed: {exc}"

    return final_content, events, status, error_code


def run_telegram_scenario(
    backend_manager: BackendManager,
    scenario: Scenario,
    *,
    run_log_path: Path,
    port_offset: int = 0,
) -> tuple[RunResult, dict]:
    """Run one scenario through the Telegram-shaped code path."""
    chat_id = "123456"
    thread_id = "7"
    # Telegram-shaped session id triggers parse_telegram_session_id branches.
    session_id = (
        f"telegram:{chat_id}:{thread_id}:{scenario.scenario_id}-"
        f"{_dt.datetime.utcnow().strftime('%H%M%S')}"
    )
    fallback_notes = [
        "python-telegram-bot not installed in venv nor bundled in dist — "
        "real Updater polling not exercised; factory parity verified via "
        "backend binary + Telegram-shaped session id",
    ]

    handle = backend_manager.spawn(
        port_offset=port_offset,
        label=f"TG-{scenario.scenario_id}",
    )

    try:
        final_content, events, status, error_code = asyncio.run(
            _telegram_ws_turn(
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
        channel_origin=f"subprocess+tg-shaped-id:{handle.pid}",
        submitted_message=scenario.goal,
    )

    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(run_log_path, "w", encoding="utf-8") as fh:
        fh.write(f"=== C13 Phase 3 Telegram channel — scenario {scenario.scenario_id} ===\n")
        fh.write(f"session_id: {session_id}\n")
        fh.write(f"backend_pid: {handle.pid}\n")
        fh.write(f"backend_port: {handle.port}\n")
        fh.write(f"status: {status}\n")
        fh.write(f"error_code: {error_code}\n")
        fh.write(f"event_count: {len(events)}\n")
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
            fh.write(json.dumps(ev)[:400] + "\n")

    return result, cleanup
