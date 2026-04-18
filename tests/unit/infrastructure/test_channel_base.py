"""Channel plugin base + registry tests."""

from ds_agent.channels.base import (
    BaseChannelPlugin,
    ChannelCapabilities,
    ChannelMeta,
    DeliveryResult,
    InboundMessage,
    OutboundMessage,
)
from ds_agent.channels.registry import ChannelRegistry


class DummyPlugin(BaseChannelPlugin):
    @property
    def meta(self) -> ChannelMeta:
        return ChannelMeta(id="dummy", name="Dummy", description="Test channel")

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(max_message_length=100)

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send_text(self, msg: OutboundMessage) -> DeliveryResult:
        return DeliveryResult(success=True, message_id="1")

    def chunk_text(self, text: str) -> list[str]:
        limit = self.capabilities.max_message_length
        if len(text) <= limit:
            return [text]
        chunks = []
        while text:
            chunks.append(text[:limit])
            text = text[limit:]
        return chunks


class TestChannelBase:
    def test_meta(self):
        p = DummyPlugin()
        assert p.meta.id == "dummy"
        assert p.meta.name == "Dummy"

    def test_capabilities(self):
        p = DummyPlugin()
        assert p.capabilities.max_message_length == 100

    def test_chunk_text_short(self):
        p = DummyPlugin()
        assert p.chunk_text("hello") == ["hello"]

    def test_chunk_text_long(self):
        p = DummyPlugin()
        text = "a" * 250
        chunks = p.chunk_text(text)
        assert len(chunks) == 3
        assert len(chunks[0]) == 100
        assert len(chunks[1]) == 100
        assert len(chunks[2]) == 50

    async def test_send_text(self):
        p = DummyPlugin()
        result = await p.send_text(OutboundMessage(text="hi", conversation_id="c1"))
        assert result.success


class TestInboundOutboundMessages:
    def test_inbound_message(self):
        msg = InboundMessage(
            channel_id="telegram",
            account_id="bot123",
            conversation_id="chat456",
            sender_id="user789",
            text="Analyze my data",
        )
        assert msg.channel_id == "telegram"
        assert msg.text == "Analyze my data"

    def test_outbound_message(self):
        msg = OutboundMessage(text="Results here", conversation_id="chat456")
        assert msg.text == "Results here"


class TestChannelRegistry:
    def test_register_and_get(self):
        registry = ChannelRegistry()
        plugin = DummyPlugin()
        registry.register(plugin)

        assert "dummy" in registry.list_channels()
        assert registry.get("dummy") is plugin

    def test_get_unknown_returns_none(self):
        registry = ChannelRegistry()
        assert registry.get("nonexistent") is None

    def test_register_multiple(self):
        registry = ChannelRegistry()
        registry.register(DummyPlugin())
        assert len(registry.list_channels()) == 1
