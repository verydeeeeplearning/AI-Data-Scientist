"""Tests for gateway/session_manager.py."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from ds_agent.gateway.session_manager import GatewaySession, SessionManager


class TestSessionManager:
    def test_create_new_session(self):
        mgr = SessionManager()
        factory = MagicMock(return_value=MagicMock(name="agent1"))

        session = asyncio.run(mgr.get_or_create("telegram", "chat1", factory))

        factory.assert_called_once()
        assert isinstance(session, GatewaySession)
        assert session.channel_id == "telegram"
        assert session.conversation_id == "chat1"
        assert session.thread_id is None

    def test_get_existing_session_reuses_agent(self):
        mgr = SessionManager()
        factory = MagicMock(return_value=MagicMock(name="agent1"))

        async def _run():
            s1 = await mgr.get_or_create("telegram", "chat1", factory)
            s2 = await mgr.get_or_create("telegram", "chat1", factory)
            return s1, s2

        s1, s2 = asyncio.run(_run())
        factory.assert_called_once()
        assert s1 is s2

    def test_last_active_updated_on_access(self):
        mgr = SessionManager()
        factory = MagicMock(return_value=MagicMock())

        async def _run():
            s1 = await mgr.get_or_create("telegram", "chat1", factory)
            first_active = s1.last_active

            import time

            time.sleep(0.01)

            s2 = await mgr.get_or_create("telegram", "chat1", factory)
            return first_active, s2.last_active

        first_active, last_active = asyncio.run(_run())
        assert last_active >= first_active

    def test_active_count(self):
        mgr = SessionManager()
        factory = MagicMock(return_value=MagicMock())

        async def _run():
            await mgr.get_or_create("telegram", "chat1", factory)
            await mgr.get_or_create("telegram", "chat2", factory)
            await mgr.get_or_create("discord", "chat1", factory)

        asyncio.run(_run())
        assert mgr.active_count() == 3

    def test_cleanup_idle_removes_expired(self):
        mgr = SessionManager()
        factory = MagicMock(return_value=MagicMock())

        session = asyncio.run(mgr.get_or_create("telegram", "chat1", factory))
        # Set last_active to long past (> 3600s ago)
        session.last_active = 0.0

        removed = mgr.cleanup_idle()
        assert removed == 1
        assert mgr.active_count() == 0

    def test_cleanup_idle_preserves_active(self):
        mgr = SessionManager()
        factory = MagicMock(return_value=MagicMock())

        asyncio.run(mgr.get_or_create("telegram", "chat1", factory))
        # Session is fresh — should not be cleaned

        removed = mgr.cleanup_idle()
        assert removed == 0
        assert mgr.active_count() == 1

    def test_session_key_format(self):
        mgr = SessionManager()
        factory = MagicMock(return_value=MagicMock())

        session = asyncio.run(mgr.get_or_create("telegram", "chat42", factory))
        assert session.session_key == "telegram:chat42"

    def test_topic_session_key_format(self):
        mgr = SessionManager()
        factory = MagicMock(return_value=MagicMock())

        session = asyncio.run(
            mgr.get_or_create("telegram", "chat42", factory, thread_id="99")
        )
        assert session.session_key == "telegram:chat42:99"
        assert session.thread_id == "99"

    def test_different_channels_different_sessions(self):
        mgr = SessionManager()
        factory = MagicMock(return_value=MagicMock())

        async def _run():
            s1 = await mgr.get_or_create("telegram", "chat1", factory)
            s2 = await mgr.get_or_create("discord", "chat1", factory)
            return s1, s2

        s1, s2 = asyncio.run(_run())
        assert s1 is not s2
        assert factory.call_count == 2

    def test_same_chat_different_topics_are_distinct_sessions(self):
        mgr = SessionManager()
        factory = MagicMock(return_value=MagicMock())

        async def _run():
            s1 = await mgr.get_or_create("telegram", "chat1", factory, thread_id="101")
            s2 = await mgr.get_or_create("telegram", "chat1", factory, thread_id="202")
            return s1, s2

        s1, s2 = asyncio.run(_run())
        assert s1 is not s2
        assert s1.session_key == "telegram:chat1:101"
        assert s2.session_key == "telegram:chat1:202"
        assert factory.call_count == 2
