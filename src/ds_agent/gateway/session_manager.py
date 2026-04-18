"""Gateway session manager — one agent per conversation."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import structlog

from ds_agent.runtime.channel_identity import telegram_session_id

logger = structlog.get_logger()


@dataclass
class GatewaySession:
    """A conversation or thread session with its own agent instance."""

    session_key: str
    agent: object  # DSAgent instance
    channel_id: str
    conversation_id: str
    thread_id: str | None = None
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)


class SessionManager:
    """Manages per-conversation or per-thread agent sessions."""

    IDLE_TIMEOUT = 3600  # 1 hour

    def __init__(self) -> None:
        self._sessions: dict[str, GatewaySession] = {}
        # 3.10 fix: prevent concurrent get_or_create from creating duplicate sessions
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        channel_id: str,
        conversation_id: str,
        agent_factory: object,
        thread_id: str | None = None,
    ) -> GatewaySession:
        """Get existing session or create new one (async-safe)."""
        key = self._session_key(channel_id, conversation_id, thread_id)

        async with self._lock:
            if key in self._sessions:
                session = self._sessions[key]
                session.last_active = time.time()
                return session

            # Create new agent via factory
            agent = agent_factory()  # type: ignore[operator]
            session = GatewaySession(
                session_key=key,
                agent=agent,
                channel_id=channel_id,
                conversation_id=conversation_id,
                thread_id=thread_id,
            )
            self._sessions[key] = session
            logger.info("session_created", key=key)
            return session

    @staticmethod
    def _session_key(channel_id: str, conversation_id: str, thread_id: str | None) -> str:
        if channel_id == "telegram":
            return telegram_session_id(conversation_id, thread_id)
        if thread_id is None:
            return f"{channel_id}:{conversation_id}"
        return f"{channel_id}:{conversation_id}:{thread_id}"

    def active_count(self) -> int:
        return len(self._sessions)

    def cleanup_idle(self) -> int:
        """Remove idle sessions. Returns count removed."""
        now = time.time()
        expired = [
            key for key, s in self._sessions.items() if now - s.last_active > self.IDLE_TIMEOUT
        ]
        for key in expired:
            del self._sessions[key]
        if expired:
            logger.info("sessions_cleaned", count=len(expired))
        return len(expired)

    async def start_cleanup_task(self, interval_seconds: int = 900) -> None:
        """Start background periodic cleanup of idle sessions (3.8 fix).

        Call once at gateway startup. Runs every interval_seconds (default 15 min).
        """

        async def _loop() -> None:
            while True:
                await asyncio.sleep(interval_seconds)
                self.cleanup_idle()

        self._cleanup_task: asyncio.Task = asyncio.create_task(_loop())
        logger.info("session_cleanup_scheduled", interval_seconds=interval_seconds)
