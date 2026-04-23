"""Telegram message builder — boundary adapter for Notification → text + markup.

Responsibilities (PLAN_04 Sub-Phase 4.5):

1. **Truncation**: messages exceeding Telegram's 4096-char limit collapse
   to a 3-line summary plus a "Open in Electron" deep-link button.
2. **PII masking**: when ``Notification.sensitive`` is True, route body
   text through :class:`PIIDetector.redact` and mask values whose column
   names match the sensitive-keyword set (email/ssn/phone/password/...).
3. **Deep link integration**: prefer
   :func:`ds_agent.domain.value_objects.deep_link.build_deep_link_uri`
   when available; otherwise fall back to a stable placeholder format.
   This wire-format MUST stay aligned with the Electron deep-link parser
   (W4-C output: ``ds-agent://workspace/<ws>/run/<run>``).

PII detection lives in infrastructure (``pii_detector.py``).  Domain
``Notification`` only carries a ``sensitive`` flag so the boundary can
make the redaction decision — domain stays free of PII regexes.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from ds_agent.domain.notification import (
    InlineButton,
    Notification,
    NotificationCategory,
)
from ds_agent.infrastructure.pii_detector import PIIDetector

TELEGRAM_MAX_MESSAGE_CHARS = 4096
SUMMARY_MAX_LINES = 3
SENSITIVE_KEYWORDS: frozenset[str] = frozenset(
    {
        "email",
        "ssn",
        "phone",
        "mobile",
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "credit_card",
        "card_number",
    }
)
_DEEP_LINK_FALLBACK = "ds-agent://workspace/{workspace}/run/{run}"

_CATEGORY_PREFIX: dict[NotificationCategory, str] = {
    NotificationCategory.INFO: "[INFO]",
    NotificationCategory.MILESTONE: "[MILESTONE]",
    NotificationCategory.ERROR: "[ERROR]",
    NotificationCategory.APPROVAL: "[APPROVAL]",
    NotificationCategory.DIGEST: "[DIGEST]",
}


@dataclass(slots=True)
class BuiltMessage:
    """Adapter output: ready to hand to Telegram ``send_text``."""

    text: str
    reply_markup: dict[str, list[list[dict[str, str]]]] | None
    truncated: bool
    masked: bool


class TelegramMessageBuilder:
    """Build a Telegram-ready message from a domain :class:`Notification`."""

    def __init__(
        self,
        *,
        pii_detector: PIIDetector | None = None,
        masking_enabled: bool = True,
    ) -> None:
        self._pii = pii_detector or PIIDetector()
        self._masking_enabled = masking_enabled

    def build(self, notification: Notification) -> BuiltMessage:
        body, masked = self._mask_body(notification)
        text = self._format_text(notification, body)

        truncated = False
        if len(text) > TELEGRAM_MAX_MESSAGE_CHARS:
            text = self._summarise(notification, body)
            truncated = True

        markup = self._build_reply_markup(notification, truncated=truncated)
        return BuiltMessage(
            text=text,
            reply_markup=markup,
            truncated=truncated,
            masked=masked,
        )

    # ------------------------------------------------------------------
    # Masking
    # ------------------------------------------------------------------

    def _mask_body(self, notification: Notification) -> tuple[str, bool]:
        if not self._masking_enabled or not notification.sensitive:
            return notification.body, False

        masked_body = self._pii.redact(notification.body)
        # Even when no regex matches, we also mask `key: value` pairs whose
        # key looks like a sensitive column name.  This catches cases like
        # `password: hunter2` that don't trip any regex.
        masked_body = _mask_sensitive_keys(masked_body)
        changed = masked_body != notification.body
        return masked_body, changed

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _format_text(self, notification: Notification, body: str) -> str:
        prefix = _CATEGORY_PREFIX.get(notification.category, "")
        title = f"{prefix} {notification.title}".strip()
        parts = [title, body.strip()] if body.strip() else [title]
        if notification.deep_link and notification.category is not NotificationCategory.APPROVAL:
            parts.append(f"Open: {notification.deep_link}")
        return "\n".join(parts)

    def _summarise(self, notification: Notification, body: str) -> str:
        prefix = _CATEGORY_PREFIX.get(notification.category, "")
        title = f"{prefix} {notification.title}".strip()
        summary_lines = _take_first_lines(body, SUMMARY_MAX_LINES)
        deep_link = notification.deep_link or _build_fallback_deep_link(notification)
        tail = f"... (truncated — open in Electron: {deep_link})"
        text = "\n".join([title, *summary_lines, tail])
        if len(text) > TELEGRAM_MAX_MESSAGE_CHARS:
            # Last resort: hard-truncate from the end while keeping deep link.
            keep = TELEGRAM_MAX_MESSAGE_CHARS - len(tail) - len(title) - 2
            condensed = body[: max(keep, 0)].rstrip()
            text = "\n".join([title, condensed, tail])
            text = text[:TELEGRAM_MAX_MESSAGE_CHARS]
        return text

    # ------------------------------------------------------------------
    # Inline keyboard
    # ------------------------------------------------------------------

    def _build_reply_markup(
        self,
        notification: Notification,
        *,
        truncated: bool,
    ) -> dict[str, list[list[dict[str, str]]]] | None:
        rows: list[list[dict[str, str]]] = []

        for button in notification.inline_keyboard:
            rows.append([_button_to_dict(button)])

        deep_link = notification.deep_link or (
            _build_fallback_deep_link(notification) if truncated else None
        )
        if deep_link is not None:
            already_present = any(
                row[0].get("url") == deep_link for row in rows if row
            )
            if not already_present:
                rows.append([{"text": "Open in Electron", "url": deep_link}])

        if not rows:
            return None
        return {"inline_keyboard": rows}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _button_to_dict(button: InlineButton) -> dict[str, str]:
    out: dict[str, str] = {"text": button.text}
    if button.callback_data is not None:
        out["callback_data"] = button.callback_data
    if button.url is not None:
        out["url"] = button.url
    return out


def _take_first_lines(text: str, n: int) -> list[str]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return lines[:n]


_SENSITIVE_KV_RE = re.compile(
    r"\b(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*(?P<val>[^\s,;]+)",
)


def _mask_sensitive_keys(text: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        key = match.group("key").lower()
        if key in SENSITIVE_KEYWORDS:
            return f"{match.group('key')}: [REDACTED_{key.upper()}]"
        return match.group(0)

    return _SENSITIVE_KV_RE.sub(_repl, text)


def _build_fallback_deep_link(notification: Notification) -> str:
    """Build a deep-link URI for a run notification.

    Prefers ``domain.value_objects.deep_link.build_deep_link_uri`` (W4-C
    output, byte-identical to the renderer's ``buildDeepLinkUri``).  Falls
    back to a stable placeholder format that matches the parser contract
    when the module is unavailable (early-bring-up only).  See PLAN_04 §8
    for the cross-PLAN dependency.
    """
    workspace = notification.workspace_id or "default"
    run = notification.run_id or "unknown"
    try:
        from ds_agent.domain.value_objects.deep_link import (  # type: ignore[import-not-found]
            DeepLink,
            build_deep_link_uri,
        )
    except ImportError:
        return _DEEP_LINK_FALLBACK.format(workspace=workspace, run=run)
    return build_deep_link_uri(
        DeepLink(workspace_id=workspace, resource_type="run", resource_id=run)
    )


def list_sensitive_keywords() -> Iterable[str]:
    """Expose the sensitive keyword set so settings UI can document it."""
    return iter(sorted(SENSITIVE_KEYWORDS))
