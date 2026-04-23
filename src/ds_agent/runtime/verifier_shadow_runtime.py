"""Process-local capture of legacy hook signals for verifier shadow mode."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from threading import Lock
from typing import Any

_EVENT_ALLOWLIST = {"harness.warning", "drift.detected", "verifier.auto_run"}
_shadow_events: dict[tuple[str, str | None], list[dict[str, Any]]] = defaultdict(list)
_lock = Lock()


def reset_shadow_runtime_log(session_id: str | None, run_id: str | None) -> None:
    """Reset the captured shadow-mode runtime log for one session/run key."""

    if not session_id:
        return
    with _lock:
        _shadow_events[(session_id, run_id)] = []


def record_shadow_runtime_tool(
    session_id: str | None,
    run_id: str | None,
    *,
    tool_name: str,
) -> None:
    """Record one tool execution for shadow applicability checks."""

    if not session_id:
        return
    with _lock:
        _shadow_events[(session_id, run_id)].append(
            {"event": "tool.call", "tool": tool_name}
        )


def record_shadow_runtime_event(
    session_id: str | None,
    run_id: str | None,
    *,
    event: str,
    payload: Mapping[str, Any],
) -> None:
    """Record one hook-emitted runtime event when relevant to shadow mode."""

    if not session_id or event not in _EVENT_ALLOWLIST:
        return
    entry = dict(payload)
    entry["event"] = event
    with _lock:
        _shadow_events[(session_id, run_id)].append(entry)


def snapshot_shadow_runtime_log(
    session_id: str | None,
    run_id: str | None,
) -> list[dict[str, Any]]:
    """Return a copy of the currently captured shadow-mode runtime log."""

    if not session_id:
        return []
    with _lock:
        exact = deepcopy(_shadow_events.get((session_id, run_id), []))
        if exact:
            return exact
        return deepcopy(_shadow_events.get((session_id, None), []))
