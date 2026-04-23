"""Notification value object and category enum.

PLAN_04 §4 data model.  Domain-pure: no I/O, no framework, no external deps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class NotificationCategory(StrEnum):
    """Five-bucket categorisation per PLAN_04 §1."""

    INFO = "info"
    MILESTONE = "milestone"
    ERROR = "error"
    APPROVAL = "approval"
    DIGEST = "digest"

    @property
    def bypasses_quiet_hours(self) -> bool:
        # ERROR / APPROVAL must reach the operator immediately even during
        # quiet hours per PLAN_04 §6 quality gate.
        return self in (NotificationCategory.ERROR, NotificationCategory.APPROVAL)


@dataclass(frozen=True, slots=True)
class InlineButton:
    """Portable inline-keyboard button.

    Adapter layer translates this into Telegram's ``InlineKeyboardButton``.
    Either ``callback_data`` (for in-bot actions like approval) or ``url``
    (for deep-link jumps) MUST be set, never both.
    """

    text: str
    callback_data: str | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("InlineButton.text must be non-empty")
        if (self.callback_data is None) == (self.url is None):
            raise ValueError(
                "InlineButton requires exactly one of callback_data or url"
            )


@dataclass(frozen=True, slots=True)
class Notification:
    """Domain notification — surface-agnostic.

    *body* is conceptually capped at 3 lines per PLAN_04 §1; enforcement
    happens at the adapter (message_builder) so domain stays pure.

    *sensitive* is an authorisation hint: when True, the adapter MUST run
    PII masking before delivery (ADR S-03 mitigation).
    """

    category: NotificationCategory
    title: str
    body: str
    deep_link: str | None = None
    inline_keyboard: tuple[InlineButton, ...] = field(default_factory=tuple)
    sensitive: bool = False
    workspace_id: str | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("Notification.title must be non-empty")
        if not isinstance(self.category, NotificationCategory):
            raise TypeError("Notification.category must be NotificationCategory")
