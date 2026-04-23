"""Helpers for serializing approval requests across runtime surfaces."""

from __future__ import annotations


def serialize_approval(approval: object) -> dict[str, object]:
    """Convert approval state to RPC/event payload format."""

    metadata = getattr(approval, "metadata", {})
    return {
        "approvalId": getattr(approval, "approval_id", ""),
        "sessionId": getattr(approval, "session_id", ""),
        "runId": getattr(approval, "run_id", None),
        "surface": getattr(approval, "surface", "unknown"),
        "question": getattr(approval, "question", ""),
        "kind": getattr(approval, "kind", "generic"),
        "metadata": dict(metadata) if isinstance(metadata, dict) else {},
        "options": list(getattr(approval, "options", []) or []),
        "default": getattr(approval, "default", None),
        "status": getattr(getattr(approval, "status", None), "value", "pending"),
        "response": getattr(approval, "response", None),
        "source": getattr(approval, "source", None),
        "actor": getattr(approval, "actor", None),
        "createdAt": getattr(approval, "created_at", 0.0),
        "updatedAt": getattr(approval, "updated_at", 0.0),
        "resolvedAt": getattr(approval, "resolved_at", None),
    }
