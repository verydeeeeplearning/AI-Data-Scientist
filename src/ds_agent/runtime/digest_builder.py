"""Digest orchestration and builder.

Builds prioritized, deduplicated digest messages from recent runtime
events.  Digests are designed to fit within Telegram's 4096-char limit
whenever possible.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field

from ds_agent.runtime.runtime_event_log import RuntimeEventLog, RuntimeEventRecord

_MAX_DIGEST_CHARS = 3800  # Leave margin for header/footer within 4096


@dataclass
class DigestSection:
    """One section within a digest message."""

    title: str
    lines: list[str] = field(default_factory=list)
    priority: int = 0  # Lower = more important


@dataclass
class DigestResult:
    """The complete digest output."""

    text: str
    event_count: int
    has_unresolved: bool


def build_digest(
    event_log: RuntimeEventLog,
    *,
    since: float | None = None,
    limit: int = 50,
) -> DigestResult:
    """Build a prioritized digest from recent events.

    *since* is a Unix timestamp; events older than this are excluded.
    If ``None``, defaults to the last 4 hours.
    """
    if since is None:
        since = time.time() - 4 * 3600

    events = event_log.list(limit=limit)
    recent = [e for e in events if e.created_at >= since]
    return build_digest_from_events(recent)


def build_digest_from_events(events: list[RuntimeEventRecord]) -> DigestResult:
    """Build a prioritized digest directly from already-selected events."""
    recent = sorted(events, key=lambda item: item.created_at, reverse=True)

    if not recent:
        return DigestResult(text="No recent events.", event_count=0, has_unresolved=False)

    sections: list[DigestSection] = []

    # Section 1: Unresolved incidents (highest priority)
    unresolved = [
        e
        for e in recent
        if e.severity in {"error", "critical"}
        and e.kind not in {"system.resource.normal", "recovery.completed"}
    ]
    if unresolved:
        sec = DigestSection(title="Unresolved incidents", priority=0)
        for evt in unresolved[:5]:
            sec.lines.append(f"- [{evt.severity}] {evt.kind}: {_truncate(evt.message, 80)}")
        if len(unresolved) > 5:
            sec.lines.append(f"  + {len(unresolved) - 5} more")
        sections.append(sec)

    # Section 2: Recent recoveries
    recoveries = [e for e in recent if e.category == "recovery"]
    if recoveries:
        sec = DigestSection(title="Recoveries", priority=1)
        sec.lines.append(f"- {len(recoveries)} recovery event(s)")
        for evt in recoveries[:3]:
            sec.lines.append(f"  {evt.kind}: {_truncate(evt.message, 60)}")
        sections.append(sec)

    # Section 3: Suppressed noise summary
    suggestions = _suggested_next_actions(recent)
    if suggestions:
        sec = DigestSection(title="Suggested next actions", priority=2)
        for item in suggestions:
            sec.lines.append(f"- {item}")
        sections.append(sec)

    # Section 4: Suppressed noise summary
    suppressed = [e for e in recent if e.kind == "policy.suppressed"]
    if suppressed:
        reasons = Counter(str(e.metadata.get("policyReason", "unknown")) for e in suppressed)
        sec = DigestSection(title="Suppressed", priority=3)
        sec.lines.append(f"- {len(suppressed)} event(s) suppressed")
        for reason, count in reasons.most_common(3):
            sec.lines.append(f"  {reason}: {count}")
        sections.append(sec)

    # Section 5: Category summary
    category_counts = Counter(e.category or "other" for e in recent)
    if len(category_counts) > 1:
        sec = DigestSection(title="By category", priority=4)
        for cat, count in category_counts.most_common(5):
            sec.lines.append(f"- {cat}: {count}")
        sections.append(sec)

    # Build final text
    sections.sort(key=lambda s: s.priority)
    parts: list[str] = [f"Digest ({len(recent)} events):"]
    total_len = len(parts[0])

    for sec in sections:
        header = f"\n{sec.title}:"
        body = "\n".join(sec.lines)
        section_text = f"{header}\n{body}"
        if total_len + len(section_text) > _MAX_DIGEST_CHARS:
            parts.append(f"\n... ({len(sections) - len(parts) + 1} sections truncated)")
            break
        parts.append(section_text)
        total_len += len(section_text)

    return DigestResult(
        text="\n".join(parts),
        event_count=len(recent),
        has_unresolved=bool(unresolved),
    )


def _truncate(text: str, limit: int) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 3].rstrip() + "..."


def _suggested_next_actions(events: list[RuntimeEventRecord]) -> list[str]:
    suggestions: list[str] = []
    if any(event.kind == "recovery.awaiting_approval" for event in events):
        suggestions.append("/approvals to resolve pending approvals")
    if any(event.kind == "recovery.resume_recommended" for event in events):
        suggestions.append("/resume to continue the latest recoverable session")

    latest_run_id = next((event.run_id for event in events if event.run_id), None)
    if latest_run_id is not None:
        suggestions.append(f"/run {latest_run_id} to inspect the latest affected run")

    if any(event.category in {"health", "pressure", "policy"} for event in events):
        suggestions.append("/alerts 10 to inspect the raw alert trail")

    if any(event.session_id for event in events):
        suggestions.append("/session to inspect checkpoint and recovery context")

    deduped: list[str] = []
    for item in suggestions:
        if item not in deduped:
            deduped.append(item)
    return deduped[:4]
