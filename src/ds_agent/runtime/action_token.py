"""Compact action tokens for Telegram inline keyboard callbacks.

Telegram limits ``callback_data`` to **64 bytes** (UTF-8).  This module
provides a compact encoding that fits action type, target id, and a
short nonce for TTL / idempotency checking within that budget.

Token format::

    {action}:{short_target}:{nonce}

Where *action* is a 2-char code, *short_target* is the first 16 chars of
the target id, and *nonce* is a 6-char hex string derived from creation
time.  The server keeps a lookup table mapping nonce → full context so
that the compact token can be resolved later.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

# 2-char action codes
ACTION_APPROVE = "ap"
ACTION_REJECT = "rj"
ACTION_STOP = "st"
ACTION_RESUME = "rs"
ACTION_INSPECT = "in"
ACTION_ACK = "ak"
ACTION_MUTE = "mu"

_ACTION_LABELS: dict[str, str] = {
    ACTION_APPROVE: "Approve",
    ACTION_REJECT: "Reject",
    ACTION_STOP: "Stop",
    ACTION_RESUME: "Resume",
    ACTION_INSPECT: "Inspect",
    ACTION_ACK: "Ack",
    ACTION_MUTE: "Mute",
}

_DEFAULT_TTL_SECONDS = 3600.0  # 1 hour


@dataclass(frozen=True, slots=True)
class ActionContext:
    """Server-side context stored for one action token."""

    action: str
    target_id: str
    actor: str
    chat_id: str
    created_at: float
    ttl_seconds: float = _DEFAULT_TTL_SECONDS


class ActionTokenStore:
    """In-memory store that maps compact tokens to full action context."""

    def __init__(self) -> None:
        self._tokens: dict[str, ActionContext] = {}

    def create(
        self,
        action: str,
        target_id: str,
        *,
        actor: str = "",
        chat_id: str = "",
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
    ) -> str:
        """Create a compact token string (fits in 64 bytes)."""
        now = time.time()
        nonce = hashlib.md5(f"{action}:{target_id}:{now}".encode()).hexdigest()[:6]
        short_target = target_id[:16]
        token = f"{action}:{short_target}:{nonce}"
        self._tokens[token] = ActionContext(
            action=action,
            target_id=target_id,
            actor=actor,
            chat_id=chat_id,
            created_at=now,
            ttl_seconds=ttl_seconds,
        )
        self._trim()
        return token

    def resolve(self, token: str) -> ActionContext | None:
        """Look up and validate a token.  Returns ``None`` if expired or unknown."""
        ctx = self._tokens.get(token)
        if ctx is None:
            return None
        if time.time() - ctx.created_at > ctx.ttl_seconds:
            del self._tokens[token]
            return None
        return ctx

    def consume(self, token: str) -> ActionContext | None:
        """Resolve and remove a token (one-time use)."""
        ctx = self.resolve(token)
        if ctx is not None:
            self._tokens.pop(token, None)
        return ctx

    def _trim(self) -> None:
        """Remove expired tokens when the store grows too large."""
        if len(self._tokens) <= 500:
            return
        now = time.time()
        expired = [k for k, v in self._tokens.items() if now - v.created_at > v.ttl_seconds]
        for k in expired:
            del self._tokens[k]


def action_label(action: str) -> str:
    """Human-readable label for a 2-char action code."""
    return _ACTION_LABELS.get(action, action)
