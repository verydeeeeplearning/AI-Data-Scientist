"""Canonical channel-aware session identity helpers.

Every Telegram session id must be produced by ``telegram_session_id`` and
parsed by ``parse_telegram_session_id``.  No caller should manually
concatenate ``"telegram:"`` with a chat id.

Format rules
------------
- DM or non-forum group (thread_id is None): ``telegram:{chat_id}``
- Forum topic (thread_id present):           ``telegram:{chat_id}:{thread_id}``

Legacy data written as ``telegram:{chat_id}`` remains valid and is
returned unchanged when ``thread_id`` is ``None``.
"""

from __future__ import annotations


def telegram_session_id(
    conversation_id: str,
    thread_id: str | None = None,
) -> str:
    """Build canonical Telegram session identity string."""
    if thread_id is None:
        return f"telegram:{conversation_id}"
    return f"telegram:{conversation_id}:{thread_id}"


def parse_telegram_session_id(
    session_id: str,
) -> tuple[str, str | None]:
    """Parse a canonical id back to *(conversation_id, thread_id | None)*.

    Accepts both ``telegram:12345`` and ``telegram:12345:67890`` formats.
    """
    body = session_id.removeprefix("telegram:")
    parts = body.split(":", maxsplit=1)
    conversation_id = parts[0]
    thread_id = parts[1] if len(parts) > 1 else None
    return conversation_id, thread_id


def telegram_legacy_session_id(session_id: str) -> str | None:
    """Return the chat-scoped legacy id for a thread-aware Telegram session."""
    if not session_id.startswith("telegram:"):
        return None
    conversation_id, thread_id = parse_telegram_session_id(session_id)
    if thread_id is None:
        return None
    return telegram_session_id(conversation_id)
