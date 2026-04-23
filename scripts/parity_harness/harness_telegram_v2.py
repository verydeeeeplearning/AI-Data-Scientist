"""Telegram channel harness v2 — live polling via fake bot (S15).

Unlike ``harness_telegram.py`` (which only wired a Telegram-shaped session
id through the backend WS), this harness actually exercises
``python-telegram-bot`` objects end-to-end offline:

    1. Build a real :class:`telegram.ext.Application` using a fake token
       (``"1:TEST_FAKE_TOKEN..."``), with ``updater=None`` so no real
       long-poll is started.
    2. Monkey-patch every outbound ``Bot.send_*`` method to a no-op that
       records the call (zero real Telegram API traffic).
    3. Instantiate the production ``TelegramPlugin`` (same class the
       ``TelegramGatewayRunner`` uses) and swap its internal ``_app`` with
       the fake Application.
    4. Construct a real ``telegram.Update`` object via ``Update.de_json``
       (the same factory python-telegram-bot uses for inbound updates
       from Telegram's servers) and invoke the plugin's registered
       ``_on_text`` handler directly. The plugin pushes an
       ``InboundMessage`` onto its queue exactly as production does.
    5. Pop the ``InboundMessage``, derive the session id via
       ``telegram_session_id(conv_id, thread_id)`` — the canonical helper
       ``TelegramGatewayRunner`` uses — and dispatch ``chat.send`` over
       the backend WebSocket with ``surface="telegram"``.
    6. Record every step (Update, handler invocation, inbound enqueued,
       session-id derivation, WS frames) to a JSONL trace.

This proves the Telegram polling → InboundMessage → session-id derivation
→ WS dispatch path using real python-telegram-bot objects and the real
``TelegramPlugin`` class, with **zero real Telegram API calls**.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import websockets
from scripts.parity_harness.backend_control import BackendHandle, BackendManager
from scripts.parity_harness.extract import RunResult, build_run_result
from scripts.parity_harness.scenarios import Scenario

logger = logging.getLogger(__name__)

FAKE_TOKEN = "1:AAAA_FAKE_TESTING_ONLY_NO_REAL_TELEGRAM_API_CALLS"


# ---------------------------------------------------------------------------
# Trace sink
# ---------------------------------------------------------------------------


@dataclass
class TraceSink:
    """Append-only JSONL trace for S15 evidence."""

    path: Path
    _events: list[dict[str, Any]] = field(default_factory=list)

    def log(self, event: str, **payload: Any) -> None:
        entry: dict[str, Any] = {
            "ts": _dt.datetime.utcnow().isoformat(timespec="microseconds") + "Z",
            "event": event,
            **payload,
        }
        self._events.append(entry)

    def dump(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            for entry in self._events:
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        self._events.clear()


# ---------------------------------------------------------------------------
# Fake bot / application wiring
# ---------------------------------------------------------------------------


class FakeBotCallRecorder:
    """Records calls to the fake bot's send methods (no network)."""

    def __init__(self, trace: TraceSink) -> None:
        self.trace = trace
        self.calls: list[dict[str, Any]] = []

    def make_sender(self, method_name: str):
        """Return an async function that swallows the call and records it."""

        async def _sender(*args: Any, **kwargs: Any) -> Any:
            record = {"method": method_name, "kwargs": {k: repr(v)[:200] for k, v in kwargs.items()}}
            self.calls.append(record)
            self.trace.log("fake_bot_call", **record)
            # Return a lightweight dummy that has a ``message_id`` attr for callers.
            return _DummyBotResult()

        return _sender


class _DummyBotResult:
    """Stand-in for a telegram ``Message`` returned by bot send methods."""

    message_id = 1


def _install_fake_bot(app: Any, recorder: FakeBotCallRecorder) -> None:
    """Monkey-patch the Application's bot so no outbound calls go to Telegram.

    ``telegram.Bot`` / ``ExtBot`` overrides ``__setattr__`` to reject direct
    assignment of API methods, so we have to use ``object.__setattr__`` to
    bypass the guard. This is exactly what ``unittest.mock`` does under
    the hood when monkey-patching slotted telegram objects.
    """
    bot = app.bot
    for name in [
        "send_message",
        "send_document",
        "send_photo",
        "answer_callback_query",
        "edit_message_text",
        "edit_message_reply_markup",
        "set_my_commands",
        "get_me",
        "get_updates",
    ]:
        object.__setattr__(bot, name, recorder.make_sender(name))


def _build_fake_application(recorder: FakeBotCallRecorder) -> Any:
    """Return an Application built with fake token and no updater/polling."""
    from telegram.ext import ApplicationBuilder

    app = ApplicationBuilder().token(FAKE_TOKEN).updater(None).build()
    _install_fake_bot(app, recorder)
    return app


def _build_update(
    *,
    chat_id: int,
    user_id: int,
    text: str,
    thread_id: int | None,
    message_id: int,
    bot: Any,
) -> Any:
    """Construct a real :class:`telegram.Update` offline via ``de_json``."""
    from telegram import Update

    payload: dict[str, Any] = {
        "update_id": message_id,
        "message": {
            "message_id": message_id,
            "date": int(_dt.datetime.utcnow().timestamp()),
            "chat": {"id": chat_id, "type": "private"},
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": "S15Tester",
            },
            "text": text,
        },
    }
    if thread_id is not None:
        payload["message"]["message_thread_id"] = thread_id
    update = Update.de_json(payload, bot)
    assert update is not None  # de_json returns None only on malformed input
    return update


# ---------------------------------------------------------------------------
# Live plugin wiring
# ---------------------------------------------------------------------------


async def _dispatch_update_through_plugin(
    scenario: Scenario,
    *,
    chat_id: int,
    user_id: int,
    thread_id: int | None,
    trace: TraceSink,
) -> tuple[Any, Any, dict[str, Any]]:
    """Instantiate real ``TelegramPlugin``, swap its app for the fake one,
    build a real Update and run ``_on_text`` on it.

    Returns ``(plugin, inbound_message, recorder_summary)`` where
    ``inbound_message`` is the ``InboundMessage`` that the plugin enqueued —
    ie the same object ``TelegramGatewayRunner._handle_message`` would
    receive in production.
    """
    from ds_agent.channels.bundled.telegram.plugin import TelegramPlugin

    recorder = FakeBotCallRecorder(trace)
    app = _build_fake_application(recorder)

    trace.log(
        "fake_application_built",
        token_prefix=FAKE_TOKEN.split(":")[0],
        bot_type=type(app.bot).__name__,
        updater=str(app.updater),
    )

    # Instantiate the real production plugin — note we never call .start(),
    # which would trigger real polling. Instead we manually splice our fake
    # Application in (same semantics as what .start() would leave behind).
    plugin = TelegramPlugin(
        bot_token=FAKE_TOKEN,
        allow_from=None,
        workspace_dir=None,
    )
    plugin._app = app  # type: ignore[attr-defined]
    plugin._running = True  # type: ignore[attr-defined]

    trace.log(
        "plugin_instantiated",
        plugin_class=type(plugin).__name__,
        fake_app_spliced=True,
    )

    # Build a real Update via de_json
    update = _build_update(
        chat_id=chat_id,
        user_id=user_id,
        text=scenario.goal,
        thread_id=thread_id,
        message_id=chat_id * 1000 + hash(scenario.scenario_id) % 1000,
        bot=app.bot,
    )
    trace.log(
        "update_constructed",
        scenario_id=scenario.scenario_id,
        update_id=update.update_id,
        message_id=update.message.message_id,
        chat_id=update.message.chat.id,
        thread_id=getattr(update.message, "message_thread_id", None),
        text_preview=update.message.text[:80] if update.message.text else "",
    )

    # Directly invoke the production ``_on_text`` handler with the real Update.
    # ``context`` is passed as None since the plugin's implementation does not
    # touch it (it reads only ``update.message``).
    await plugin._on_text(update, None)  # type: ignore[attr-defined]
    trace.log("plugin_on_text_invoked", handler="_on_text")

    # Pop the resulting InboundMessage from the plugin's queue — this is
    # exactly what ``TelegramGatewayRunner`` does in production.
    inbound = await asyncio.wait_for(plugin.get_next_message(), timeout=2.0)
    trace.log(
        "inbound_message_dequeued",
        channel_id=inbound.channel_id,
        conversation_id=inbound.conversation_id,
        thread_id=inbound.thread_id,
        sender_id=inbound.sender_id,
        text_len=len(inbound.text),
    )

    summary = {
        "fake_bot_calls_total": len(recorder.calls),
        "fake_bot_call_methods": sorted({c["method"] for c in recorder.calls}),
    }
    return plugin, inbound, summary


# ---------------------------------------------------------------------------
# WS dispatch (same shape as CLI/TG harness)
# ---------------------------------------------------------------------------


async def _telegram_ws_turn(
    handle: BackendHandle,
    *,
    user_message: str,
    session_id: str,
    trace: TraceSink,
    deadline_s: float = 30.0,
) -> tuple[str, list[dict[str, Any]], str, str]:
    events: list[dict[str, Any]] = []
    final_content = ""
    error_code = ""
    status = "ok"

    req_id = f"s15-{session_id}"
    request = {
        "type": "req",
        "id": req_id,
        "method": "chat.send",
        "params": {
            "sessionId": session_id,
            "message": user_message,
            "surface": "telegram",
            "maxIterations": 2,
            "maxCostUsd": 0.0,
        },
    }

    trace.log(
        "ws_request",
        url=handle.ws_url().split("?", 1)[0],
        request=request,
    )

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
                trace.log(
                    "ws_frame",
                    frame_type=frame.get("type"),
                    frame_event_name=frame.get("event"),
                )

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
        trace.log("ws_exception", type=type(exc).__name__, message=str(exc))

    trace.log(
        "ws_complete",
        event_count=len(events),
        status=status,
        error_code=error_code,
        final_content_len=len(final_content),
    )
    return final_content, events, status, error_code


# ---------------------------------------------------------------------------
# Top-level scenario runner
# ---------------------------------------------------------------------------


def run_telegram_live_scenario(
    backend_manager: BackendManager,
    scenario: Scenario,
    *,
    run_log_path: Path,
    trace_path: Path,
    port_offset: int = 0,
    chat_id: int = 555777,
    user_id: int = 8881,
    thread_id: int | None = 7,
) -> tuple[RunResult, dict[str, Any], dict[str, Any]]:
    """Run one scenario through the **live** Telegram path.

    Returns ``(RunResult, cleanup_info, harness_summary)``.
    ``harness_summary`` carries evidence of what the fake bot did.
    """
    trace = TraceSink(path=trace_path)
    trace.log(
        "scenario_start",
        scenario_id=scenario.scenario_id,
        goal_preview=scenario.goal[:100],
    )

    fallback_notes: list[str] = []

    # Phase 1: run the plugin-side leg offline to pop an InboundMessage.
    try:
        plugin, inbound, fake_bot_summary = asyncio.run(
            _dispatch_update_through_plugin(
                scenario,
                chat_id=chat_id,
                user_id=user_id,
                thread_id=thread_id,
                trace=trace,
            )
        )
    except Exception as exc:  # pragma: no cover - fail loud
        trace.log("plugin_dispatch_failed", error=str(exc), type=type(exc).__name__)
        trace.dump()
        raise

    # Phase 2: derive Telegram session id via canonical helper (same as
    # TelegramGatewayRunner._execute_agent_turn would).
    from ds_agent.runtime.channel_identity import telegram_session_id

    base_session_id = telegram_session_id(
        inbound.conversation_id, inbound.thread_id
    )
    # Append a short disambiguator so each scenario keeps its own session.
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

    # Phase 3: spawn backend and send chat.send over WS using surface=telegram.
    handle = backend_manager.spawn(
        port_offset=port_offset,
        label=f"TGL-{scenario.scenario_id}",
    )
    trace.log(
        "backend_spawned",
        pid=handle.pid,
        port=handle.port,
    )

    try:
        final_content, events, status, error_code = asyncio.run(
            _telegram_ws_turn(
                handle,
                user_message=inbound.text,
                session_id=session_id,
                trace=trace,
                deadline_s=45.0,
            )
        )
    finally:
        cleanup = backend_manager.stop(handle)
        trace.log(
            "backend_cleanup",
            pid=handle.pid,
            cleanup=cleanup,
        )

    if not final_content:
        final_content = "[harness] no content captured"

    if fake_bot_summary.get("fake_bot_calls_total", 0) > 0:
        fallback_notes.append(
            "fake bot recorded outbound calls (no real Telegram API traffic) — "
            f"methods={fake_bot_summary.get('fake_bot_call_methods')}"
        )
    fallback_notes.append(
        "telegram live harness: Update.de_json → TelegramPlugin._on_text → "
        "InboundMessage → telegram_session_id → WS chat.send"
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
        channel_origin=f"live:ptb_app+fake_bot+subprocess:{handle.pid}",
        submitted_message=scenario.goal,
    )

    # Persist run log
    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(run_log_path, "w", encoding="utf-8") as fh:
        fh.write(f"=== S15 Telegram LIVE channel — scenario {scenario.scenario_id} ===\n")
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
