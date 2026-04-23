"""Integration tests for the Telegram message builder + callback handler.

PLAN_04 Sub-Phase 4.5 quality gates:
- 4096-char overflow → 3-line summary + deep-link "Open in Electron" button
- PII masking applied when ``Notification.sensitive=True``
- Inline keyboard preserved (approval buttons + Open in Electron)
"""

from __future__ import annotations

import asyncio

import pytest

from ds_agent.channels.bundled.telegram.callback_handler import (
    ApprovalSubmitOutcome,
    ApprovalSubmitterPort,
    CallbackParseError,
    TelegramApprovalCallbackHandler,
    parse_approval_callback,
)
from ds_agent.channels.bundled.telegram.message_builder import (
    SUMMARY_MAX_LINES,
    TELEGRAM_MAX_MESSAGE_CHARS,
    TelegramMessageBuilder,
)
from ds_agent.domain.notification import (
    InlineButton,
    Notification,
    NotificationCategory,
)


def test_short_message_passes_through() -> None:
    builder = TelegramMessageBuilder()
    n = Notification(
        category=NotificationCategory.MILESTONE,
        title="Phase 3 done",
        body="all good",
    )
    out = builder.build(n)
    assert out.truncated is False
    assert out.masked is False
    assert "Phase 3 done" in out.text
    assert "[MILESTONE]" in out.text


def test_long_message_truncated_to_summary_with_deep_link() -> None:
    builder = TelegramMessageBuilder()
    body = "\n".join([f"line{i:04d} " + ("x" * 80) for i in range(200)])
    assert len(body) > TELEGRAM_MAX_MESSAGE_CHARS
    n = Notification(
        category=NotificationCategory.INFO,
        title="Big result",
        body=body,
        workspace_id="ws-42",
        run_id="run-7",
    )
    out = builder.build(n)
    assert out.truncated is True
    assert len(out.text) <= TELEGRAM_MAX_MESSAGE_CHARS
    assert "truncated" in out.text
    assert "ds-agent://workspace/ws-42/run/run-7" in out.text
    # Summary keeps at most SUMMARY_MAX_LINES of body content.
    summary_block = out.text.split("\n")[1 : 1 + SUMMARY_MAX_LINES]
    assert len(summary_block) <= SUMMARY_MAX_LINES
    assert out.reply_markup is not None
    buttons = out.reply_markup["inline_keyboard"]
    assert any(any(b.get("text") == "Open in Electron" for b in row) for row in buttons)


def test_truncation_uses_existing_deep_link_when_provided() -> None:
    builder = TelegramMessageBuilder()
    body = "x" * (TELEGRAM_MAX_MESSAGE_CHARS + 100)
    n = Notification(
        category=NotificationCategory.INFO,
        title="Big",
        body=body,
        deep_link="ds-agent://workspace/custom/run/abc",
    )
    out = builder.build(n)
    assert out.truncated is True
    assert "ds-agent://workspace/custom/run/abc" in out.text


def test_pii_masking_redacts_email_phone_ssn_when_sensitive() -> None:
    builder = TelegramMessageBuilder()
    body = "Customer alice@example.com called from 415-555-1212.\nSSN: 123-45-6789, balance $42."
    n = Notification(
        category=NotificationCategory.INFO,
        title="Audit alert",
        body=body,
        sensitive=True,
    )
    out = builder.build(n)
    assert out.masked is True
    assert "alice@example.com" not in out.text
    assert "415-555-1212" not in out.text
    assert "123-45-6789" not in out.text
    assert "REDACTED" in out.text


def test_pii_masking_skipped_when_not_sensitive() -> None:
    builder = TelegramMessageBuilder()
    n = Notification(
        category=NotificationCategory.INFO,
        title="benign",
        body="contact: alice@example.com",
        sensitive=False,
    )
    out = builder.build(n)
    assert out.masked is False
    assert "alice@example.com" in out.text


def test_password_token_masked_via_keyword() -> None:
    builder = TelegramMessageBuilder()
    n = Notification(
        category=NotificationCategory.INFO,
        title="creds",
        body="password: hunter2 token=abcdef api_key: 9999",
        sensitive=True,
    )
    out = builder.build(n)
    assert "hunter2" not in out.text
    assert "abcdef" not in out.text
    assert "9999" not in out.text
    assert "REDACTED_PASSWORD" in out.text
    assert "REDACTED_TOKEN" in out.text or "REDACTED_API_KEY" in out.text


def test_masking_disabled_globally() -> None:
    builder = TelegramMessageBuilder(masking_enabled=False)
    n = Notification(
        category=NotificationCategory.INFO,
        title="t",
        body="email: alice@example.com",
        sensitive=True,
    )
    out = builder.build(n)
    assert out.masked is False
    assert "alice@example.com" in out.text


def test_inline_keyboard_preserved_for_approval() -> None:
    builder = TelegramMessageBuilder()
    n = Notification(
        category=NotificationCategory.APPROVAL,
        title="Approve deploy?",
        body="risk: medium",
        deep_link="ds-agent://workspace/ws/run/r1",
        inline_keyboard=(
            InlineButton(text="Approve", callback_data="approval:approve:a1"),
            InlineButton(text="Reject", callback_data="approval:reject:a1"),
        ),
    )
    out = builder.build(n)
    assert out.reply_markup is not None
    rows = out.reply_markup["inline_keyboard"]
    flat = [b for row in rows for b in row]
    assert any(b.get("callback_data") == "approval:approve:a1" for b in flat)
    assert any(b.get("callback_data") == "approval:reject:a1" for b in flat)
    assert any(b.get("url", "").startswith("ds-agent://") for b in flat)


def test_deep_link_button_not_duplicated_when_already_provided() -> None:
    builder = TelegramMessageBuilder()
    deep_link = "ds-agent://workspace/ws/run/r1"
    n = Notification(
        category=NotificationCategory.APPROVAL,
        title="Approve",
        body="b",
        deep_link=deep_link,
        inline_keyboard=(InlineButton(text="Open in Electron", url=deep_link),),
    )
    out = builder.build(n)
    assert out.reply_markup is not None
    rows = out.reply_markup["inline_keyboard"]
    open_buttons = [b for row in rows for b in row if b.get("url") == deep_link]
    assert len(open_buttons) == 1


# ---------------------------------------------------------------------------
# Callback handler
# ---------------------------------------------------------------------------


def test_parse_approval_callback_basic() -> None:
    parsed = parse_approval_callback("approval:approve:abc-123")
    assert parsed.decision == "approve"
    assert parsed.approval_id == "abc-123"
    assert parsed.reason is None


def test_parse_approval_callback_with_reason() -> None:
    parsed = parse_approval_callback("approval:reject:abc-123:looks%20bad")
    assert parsed.reason == "looks bad"


def test_parse_approval_callback_rejects_garbage() -> None:
    with pytest.raises(CallbackParseError):
        parse_approval_callback("nope:bad")
    with pytest.raises(CallbackParseError):
        parse_approval_callback("approval:explode:a1")
    with pytest.raises(CallbackParseError):
        parse_approval_callback("approval:approve:")


class _FakeSubmitter(ApprovalSubmitterPort):
    def __init__(
        self,
        *,
        success: bool = True,
        delay: float = 0.0,
        message: str = "ok",
    ) -> None:
        self._success = success
        self._delay = delay
        self._message = message
        self.calls: list[dict[str, object]] = []

    async def submit(
        self,
        *,
        approval_id: str,
        decision: str,
        operator_id: str,
        reason: str | None,
    ) -> ApprovalSubmitOutcome:
        self.calls.append(
            {
                "approval_id": approval_id,
                "decision": decision,
                "operator_id": operator_id,
                "reason": reason,
            }
        )
        if self._delay:
            await asyncio.sleep(self._delay)
        return ApprovalSubmitOutcome(
            success=self._success, message=self._message, new_status="approved"
        )


def test_callback_handler_happy_path() -> None:
    submitter = _FakeSubmitter()
    handler = TelegramApprovalCallbackHandler(submitter)
    result = asyncio.run(handler.handle(callback_data="approval:approve:a1", operator_id="op1"))
    assert result.handled is True
    assert "Approved" in result.user_visible_text
    assert submitter.calls[0]["approval_id"] == "a1"
    assert result.elapsed_seconds < 2.0


def test_callback_handler_parse_error_returns_user_visible() -> None:
    submitter = _FakeSubmitter()
    handler = TelegramApprovalCallbackHandler(submitter)
    result = asyncio.run(handler.handle(callback_data="garbage", operator_id="op1"))
    assert result.handled is False
    assert "Bad action" in result.user_visible_text
    assert submitter.calls == []


def test_callback_handler_times_out_after_budget() -> None:
    # delay > budget → asyncio.wait_for raises and we return a soft response.
    submitter = _FakeSubmitter(delay=3.0)
    late_logged: list[float] = []

    async def _on_late(elapsed: float) -> None:
        late_logged.append(elapsed)

    handler = TelegramApprovalCallbackHandler(submitter)
    result = asyncio.run(
        handler.handle(
            callback_data="approval:approve:a1",
            operator_id="op1",
            on_late=_on_late,
        )
    )
    assert result.handled is False
    assert "shortly" in result.user_visible_text.lower()
    assert late_logged and late_logged[0] >= 2.0


def test_callback_handler_failure_outcome_surfaces_message() -> None:
    submitter = _FakeSubmitter(success=False, message="not allowed")
    handler = TelegramApprovalCallbackHandler(submitter)
    result = asyncio.run(handler.handle(callback_data="approval:reject:a1", operator_id="op1"))
    assert result.handled is True
    assert "not allowed" in result.user_visible_text
