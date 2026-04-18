"""Channel plugin registry — discover, load, manage channels."""

from __future__ import annotations

import structlog

from ds_agent.channels.base import BaseChannelPlugin

logger = structlog.get_logger()


class ChannelRegistry:
    """Registry for channel plugins."""

    def __init__(self) -> None:
        self._channels: dict[str, BaseChannelPlugin] = {}

    def register(self, plugin: BaseChannelPlugin) -> None:
        self._channels[plugin.meta.id] = plugin

    def get(self, channel_id: str) -> BaseChannelPlugin | None:
        return self._channels.get(channel_id)

    def list_channels(self) -> list[str]:
        return list(self._channels.keys())

    async def start_all(self) -> None:
        for plugin in self._channels.values():
            await plugin.start()

    async def stop_all(self) -> None:
        # 4.13 fix: continue stopping remaining channels even if one fails
        for plugin in self._channels.values():
            try:
                await plugin.stop()
            except Exception:
                logger.warning("channel_stop_failed", channel=plugin.meta.id, exc_info=True)
