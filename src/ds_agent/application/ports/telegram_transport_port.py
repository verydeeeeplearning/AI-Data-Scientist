"""Application-layer Telegram transport port.

Concrete adapters translate this protocol into Telegram Bot API calls. The
application layer depends only on these DTOs and protocol methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class BotIdentity:
    """Minimal identity returned by Telegram ``getMe``."""

    id: int
    username: str
    first_name: str | None = None

    def __post_init__(self) -> None:
        if self.id <= 0:
            raise ValueError("bot id must be positive")
        username = self.username.strip().removeprefix("@")
        if not username:
            raise ValueError("bot username must be non-empty")
        object.__setattr__(self, "username", username)
        if self.first_name is not None:
            stripped_first_name = self.first_name.strip()
            object.__setattr__(
                self,
                "first_name",
                stripped_first_name or None,
            )


@runtime_checkable
class TelegramTransportPort(Protocol):
    """Output port for the subset of Telegram API calls used by setup flows."""

    async def get_me(self, token: str) -> BotIdentity:
        """Validate *token* and return the bot identity."""

    async def send_message(self, *, token: str, chat_id: str, text: str) -> None:
        """Send a plain text message through the bot token."""

