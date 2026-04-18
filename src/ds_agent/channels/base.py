"""Base channel plugin — abstract interface for all messaging platforms."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChannelCapabilities:
    """Declares what a channel supports."""

    threads: bool = False
    media: bool = False
    markdown: bool = False
    reactions: bool = False
    max_message_length: int = 4096
    streaming: bool = False


@dataclass
class ChannelMeta:
    """Channel identity."""

    id: str
    name: str
    description: str
    version: str = "0.1.0"


@dataclass
class InboundMessage:
    """Message received from a platform."""

    channel_id: str
    account_id: str
    conversation_id: str
    sender_id: str
    text: str
    thread_id: str | None = None
    reply_to_id: str | None = None
    media: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    callback_data: str | None = None
    callback_query_id: str | None = None
    source_message_id: str | None = None


@dataclass
class OutboundMessage:
    """Message to send to a platform."""

    text: str
    conversation_id: str
    thread_id: str | None = None
    reply_to_id: str | None = None
    media: list[dict] = field(default_factory=list)
    parse_mode: str = "markdown"
    reply_markup: object | None = None


@dataclass
class DeliveryResult:
    """Result of sending a message."""

    success: bool
    message_id: str | None = None
    error: str | None = None


class BaseChannelPlugin(ABC):
    """Abstract base for all channel plugins."""

    @property
    @abstractmethod
    def meta(self) -> ChannelMeta: ...

    @property
    @abstractmethod
    def capabilities(self) -> ChannelCapabilities: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def send_text(self, msg: OutboundMessage) -> DeliveryResult: ...

    def chunk_text(self, text: str) -> list[str]:
        """Split text to fit channel's max message length."""
        limit = self.capabilities.max_message_length
        # 4.13 fix: limit=0 would cause an infinite loop — return as-is
        if limit <= 0:
            return [text] if text else []
        if len(text) <= limit:
            return [text]
        chunks = []
        while text:
            if len(text) <= limit:
                chunks.append(text)
                break
            split_at = text.rfind("\n", 0, limit)
            if split_at == -1:
                split_at = limit
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return chunks
