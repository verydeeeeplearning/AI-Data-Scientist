"""Channel-agnostic result extraction + normalisation for parity diffing.

Given a raw run record (dict of events / final content) produces a
normalised ``RunResult`` whose non-infrastructure fields must be
identical across CLI / Telegram / Electron for the same scenario.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RunResult:
    """Normalised output for a single (channel × scenario) run."""

    channel: str  # CLI | Telegram | Electron
    scenario_id: str
    session_id: str
    status: str  # ok | error
    # Non-infrastructure fields (must match across channels)
    goal_echo: str = ""
    final_verdict: str = ""
    delivery_pack_body_hash: str = ""
    delivery_pack_body_preview: str = ""
    metric_spec: dict[str, Any] = field(default_factory=dict)
    error_code: str = ""
    # Infrastructure fields (allowed to differ)
    channel_origin: str = ""
    timestamp_utc: str = ""
    # Raw fields retained for audit
    raw_final_content: str = ""
    raw_event_count: int = 0
    raw_event_types: list[str] = field(default_factory=list)
    fallback_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalise markdown/text for cross-channel hashing.

    Collapses whitespace, strips timestamps/session IDs/random hex.
    """
    if not text:
        return ""
    normalised = _WHITESPACE_RE.sub(" ", text).strip()
    # strip hex tokens that could be session_id-ish
    normalised = re.sub(r"\b[0-9a-fA-F]{8,}\b", "<HEX>", normalised)
    # strip ISO8601 timestamps
    normalised = re.sub(
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?Z?",
        "<TS>",
        normalised,
    )
    return normalised


def hash_body(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def build_run_result(
    *,
    channel: str,
    scenario_id: str,
    session_id: str,
    status: str,
    final_content: str,
    events: list[dict[str, Any]] | None = None,
    error_code: str = "",
    fallback_notes: list[str] | None = None,
    timestamp_utc: str = "",
    channel_origin: str = "",
    submitted_message: str = "",
) -> RunResult:
    """Build a normalised per-run result.

    ``submitted_message`` is the goal text the harness submitted — used to
    populate ``goal_echo`` even when the backend errors out before
    emitting ``task.started`` (fallback path under mocked provider).
    """
    events = events or []
    # Derive goal echo + verdict + metric_spec from events
    goal_echo = ""
    final_verdict = ""
    metric_spec: dict[str, Any] = {}
    for ev in events:
        et = str(ev.get("type") or ev.get("event") or "")
        if et == "task.started":
            msg = ev.get("payload", {}).get("message") if isinstance(ev.get("payload"), dict) else ev.get("message")
            if msg:
                goal_echo = normalize_text(str(msg))[:200]
        if et in ("task.completed", "res"):
            payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
            if isinstance(payload, dict):
                if "verdict" in payload:
                    final_verdict = str(payload["verdict"])
                if "metricSpec" in payload:
                    metric_spec = dict(payload["metricSpec"])

    # Fallback: if no task.started captured, use the submitted message so
    # goal_echo parity still holds across channels for short-circuited runs.
    if not goal_echo and submitted_message:
        goal_echo = normalize_text(submitted_message)[:200]

    return RunResult(
        channel=channel,
        scenario_id=scenario_id,
        session_id=session_id,
        status=status,
        goal_echo=goal_echo,
        final_verdict=final_verdict,
        delivery_pack_body_hash=hash_body(final_content),
        delivery_pack_body_preview=normalize_text(final_content)[:200],
        metric_spec=metric_spec,
        error_code=error_code,
        channel_origin=channel_origin,
        timestamp_utc=timestamp_utc,
        raw_final_content=final_content,
        raw_event_count=len(events),
        raw_event_types=sorted({str(e.get("type") or e.get("event") or "") for e in events}),
        fallback_notes=fallback_notes or [],
    )
