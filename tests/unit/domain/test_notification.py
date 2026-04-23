"""Tests for ds_agent.domain.notification.notification."""

from __future__ import annotations

import pytest

from ds_agent.domain.notification import (
    InlineButton,
    Notification,
    NotificationCategory,
)


def test_category_enum_has_all_five_buckets() -> None:
    values = {c.value for c in NotificationCategory}
    assert values == {"info", "milestone", "error", "approval", "digest"}


@pytest.mark.parametrize(
    "category, bypass",
    [
        (NotificationCategory.INFO, False),
        (NotificationCategory.MILESTONE, False),
        (NotificationCategory.DIGEST, False),
        (NotificationCategory.ERROR, True),
        (NotificationCategory.APPROVAL, True),
    ],
)
def test_bypass_quiet_hours_only_for_error_and_approval(
    category: NotificationCategory, bypass: bool
) -> None:
    assert category.bypasses_quiet_hours is bypass


def test_inline_button_requires_exactly_one_action() -> None:
    InlineButton(text="Approve", callback_data="approval:approve")
    InlineButton(text="Open", url="ds-agent://workspace/w1/run/r1")

    with pytest.raises(ValueError):
        InlineButton(text="Bad", callback_data="x", url="y")
    with pytest.raises(ValueError):
        InlineButton(text="Bad")
    with pytest.raises(ValueError):
        InlineButton(text="   ", callback_data="x")


def test_notification_requires_non_empty_title() -> None:
    Notification(
        category=NotificationCategory.INFO,
        title="hello",
        body="world",
    )
    with pytest.raises(ValueError):
        Notification(
            category=NotificationCategory.INFO,
            title="   ",
            body="world",
        )


def test_notification_category_must_be_enum() -> None:
    with pytest.raises(TypeError):
        Notification(
            category="info",  # type: ignore[arg-type]
            title="t",
            body="b",
        )


def test_notification_with_inline_keyboard_and_deep_link() -> None:
    n = Notification(
        category=NotificationCategory.APPROVAL,
        title="Approve deploy?",
        body="risk: medium",
        deep_link="ds-agent://workspace/ws/run/r1",
        inline_keyboard=(
            InlineButton(text="Approve", callback_data="approval:approve:a1"),
            InlineButton(text="Reject", callback_data="approval:reject:a1"),
        ),
        sensitive=True,
    )
    assert n.sensitive is True
    assert n.inline_keyboard[0].callback_data == "approval:approve:a1"
    assert n.deep_link is not None
