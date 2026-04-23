"""Approval inline-keyboard callback handler.

PLAN_04 Sub-Phase 4.3: when an operator taps an approval button on a
Telegram message, the callback_data string identifies (a) which approval
request and (b) which decision (approve/reject).  This module parses the
callback payload and forwards it to the Phase 2 PLAN_06 approval submit
use case.  Response budget: < 2s (PLAN_04 §6).

Wire-format for ``callback_data``:
    approval:<decision>:<approval_id>
    approval:<decision>:<approval_id>:<reason>

``decision`` ∈ {approve, reject}.  ``reason`` is optional and is
URL-decoded on parse; if present, callers should still keep it short
(Telegram's callback_data hard limit is 64 bytes).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import unquote

import structlog

logger = structlog.get_logger()

CALLBACK_PREFIX = "approval"
CALLBACK_RESPONSE_BUDGET_SECONDS = 2.0


class ApprovalSubmitterPort(Protocol):
    """Port to the Phase 2 PLAN_06 approval submit pipeline."""

    async def submit(
        self,
        *,
        approval_id: str,
        decision: str,
        operator_id: str,
        reason: str | None,
    ) -> ApprovalSubmitOutcome: ...


@dataclass(slots=True)
class ApprovalSubmitOutcome:
    success: bool
    message: str
    new_status: str | None = None


@dataclass(slots=True)
class ApprovalCallback:
    approval_id: str
    decision: str
    reason: str | None = None


@dataclass(slots=True)
class CallbackResult:
    handled: bool
    user_visible_text: str
    elapsed_seconds: float
    outcome: ApprovalSubmitOutcome | None = None


class CallbackParseError(ValueError):
    """Raised when callback_data does not match the approval wire-format."""


def parse_approval_callback(callback_data: str) -> ApprovalCallback:
    parts = callback_data.split(":")
    if len(parts) < 3 or parts[0] != CALLBACK_PREFIX:
        raise CallbackParseError(
            f"unrecognised callback_data: {callback_data!r}"
        )
    decision = parts[1]
    if decision not in {"approve", "reject"}:
        raise CallbackParseError(f"unknown decision: {decision!r}")
    approval_id = parts[2]
    if not approval_id:
        raise CallbackParseError("missing approval_id")
    reason = ":".join(parts[3:]) or None
    if reason is not None:
        reason = unquote(reason)
    return ApprovalCallback(
        approval_id=approval_id, decision=decision, reason=reason
    )


class TelegramApprovalCallbackHandler:
    """Async handler invoked by ``TelegramPlugin._on_callback_query``."""

    def __init__(
        self,
        submitter: ApprovalSubmitterPort,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._submitter = submitter
        self._clock = clock

    async def handle(
        self,
        *,
        callback_data: str,
        operator_id: str,
        on_late: Callable[[float], Awaitable[None]] | None = None,
    ) -> CallbackResult:
        started = self._clock()
        try:
            parsed = parse_approval_callback(callback_data)
        except CallbackParseError as exc:
            elapsed = self._clock() - started
            logger.debug("telegram_callback_parse_error", error=str(exc))
            return CallbackResult(
                handled=False,
                user_visible_text=f"Bad action: {exc}",
                elapsed_seconds=elapsed,
            )

        try:
            outcome = await asyncio.wait_for(
                self._submitter.submit(
                    approval_id=parsed.approval_id,
                    decision=parsed.decision,
                    operator_id=operator_id,
                    reason=parsed.reason,
                ),
                timeout=CALLBACK_RESPONSE_BUDGET_SECONDS,
            )
        except TimeoutError:
            elapsed = self._clock() - started
            if on_late is not None:
                await on_late(elapsed)
            logger.warning(
                "telegram_approval_callback_slow",
                approval_id=parsed.approval_id,
                elapsed=elapsed,
            )
            return CallbackResult(
                handled=False,
                user_visible_text="Still working… we'll update you shortly.",
                elapsed_seconds=elapsed,
            )

        elapsed = self._clock() - started
        if elapsed > CALLBACK_RESPONSE_BUDGET_SECONDS and on_late is not None:
            await on_late(elapsed)

        verb = "approved" if parsed.decision == "approve" else "rejected"
        text = (
            f"{verb.capitalize()} ✓"
            if outcome.success
            else f"Failed: {outcome.message}"
        )
        return CallbackResult(
            handled=True,
            user_visible_text=text,
            elapsed_seconds=elapsed,
            outcome=outcome,
        )
