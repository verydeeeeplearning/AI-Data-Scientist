"""Agent session registry — manages per-session DSAgent instances.

Extracted from AppState (4.1.4 god object decomposition).
Thread-safe agent creation and lookup with asyncio.Lock.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from ds_agent.domain.value_objects.quality_preset import detect_quality_preset
from ds_agent.runtime.authority_overlay import resolve_authority_overlay

if TYPE_CHECKING:
    from ds_agent.agent.core import DSAgent
    from ds_agent.config.schema import DSAgentConfig
    from ds_agent.domain.interfaces.llm_provider import AgentCallbacks
    from ds_agent.domain.interfaces.session_state import CheckpointStore, TranscriptStore
    from ds_agent.infrastructure.auth.token_store import AuthProfileStore
    from ds_agent.skills.hub import SkillHub

logger = structlog.get_logger()


@dataclass(slots=True)
class SessionRecord:
    """One logical chat session bound to a concrete DSAgent + model."""

    agent: DSAgent
    model_name: str
    authority_mode: str | None = None


class AgentSessionRegistry:
    """Manages session → DSAgent mapping with thread-safe creation."""

    def __init__(
        self,
        config: DSAgentConfig,
        token_store: AuthProfileStore | None = None,
        transcript_store: TranscriptStore | None = None,
        checkpoint_store: CheckpointStore | None = None,
        approval_store: object | None = None,
        skill_hub: SkillHub | None = None,
        org_policy_supplier: object | None = None,
    ) -> None:
        self._config = config
        self._token_store = token_store
        self._transcript_store = transcript_store
        self._checkpoint_store = checkpoint_store
        self._approval_store = approval_store
        self._skill_hub = skill_hub
        self._org_policy_supplier = org_policy_supplier
        self._agents: dict[str, SessionRecord] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        session_id: str,
        callbacks: AgentCallbacks,
        model: str | None = None,
    ) -> DSAgent:
        """Return existing agent for session or create a new one (thread-safe)."""
        async with self._lock:
            authority_mode = self._current_authority_overlay()
            record = self._agents.get(session_id)
            if record is not None:
                target_model = model or record.model_name
                if (
                    target_model != record.model_name
                    or authority_mode != record.authority_mode
                ):
                    agent = self._create_agent(
                        session_id,
                        callbacks,
                        target_model,
                        authority_mode=authority_mode,
                    )
                    self._agents[session_id] = SessionRecord(
                        agent=agent,
                        model_name=target_model,
                        authority_mode=authority_mode,
                    )
                    logger.info(
                        "session_agent_replaced",
                        session_id=session_id,
                        old_model=record.model_name,
                        new_model=target_model,
                        old_authority_mode=record.authority_mode,
                        new_authority_mode=authority_mode,
                    )
                    return agent

                record.agent.set_callbacks(callbacks)
                return record.agent

            model_name = model or self._config.provider.default_model
            agent = self._create_agent(
                session_id,
                callbacks,
                model_name,
                authority_mode=authority_mode,
            )
            self._agents[session_id] = SessionRecord(
                agent=agent,
                model_name=model_name,
                authority_mode=authority_mode,
            )
            return agent

    def get(self, session_id: str) -> DSAgent | None:
        """Lookup agent by session_id. Returns None if not found."""
        record = self._agents.get(session_id)
        return record.agent if record is not None else None

    @property
    def active_count(self) -> int:
        return len(self._agents)

    def get_status(self) -> dict:
        """Aggregate status for the status bar."""
        return {
            "model": self._config.provider.default_model,
            "qualityPreset": detect_quality_preset(
                self._config.provider.default_model,
                self._config.provider.fallback_models,
            ).value,
            "mode": self._config.agent.mode,
            "activeSessions": self.active_count,
        }

    def _create_agent(
        self,
        session_id: str,
        callbacks: AgentCallbacks,
        model: str | None = None,
        *,
        authority_mode: str | None = None,
    ) -> DSAgent:
        """Create a DSAgent via the shared factory."""
        from ds_agent.agent.factory import create_agent
        from ds_agent.runtime.provider_factory import create_provider_router

        model_str = model or self._config.provider.default_model
        emit_event = getattr(callbacks, "emit_event", None)
        provider_event_callback = None
        if callable(emit_event):

            def provider_event_callback(event: str, payload: dict) -> None:
                emit_event(
                    event,
                    {
                        "sessionId": session_id,
                        "surface": "ws",
                        **payload,
                    },
                )

        provider = create_provider_router(
            model_str,
            self._config,
            token_store=self._token_store,
            emit_event=provider_event_callback,
        )

        return create_agent(
            provider=provider,
            callbacks=callbacks,
            max_iterations=self._config.agent.max_iterations,
            max_cost_usd=self._config.provider.max_budget_usd,
            mode=self._config.agent.mode,
            model_name=model_str,
            workspace_dir=str(self._config.agent.workspace_dir),
            session_id=session_id,
            use_case_hint=self._config.agent.use_case_hint,
            use_case_context=self._config.agent.use_case_context,
            transcript_store=self._transcript_store,
            checkpoint_store=self._checkpoint_store,
            approval_store=self._approval_store,
            authority_mode=authority_mode,
            connector_configs={
                name: settings.to_domain() for name, settings in self._config.connectors.items()
            },
            skill_hub=self._skill_hub,
            org_policy_supplier=self._org_policy_supplier,
            sandbox_config=self._config.sandbox,
            language=getattr(self._config.agent, "language", None),
        )

    def _current_authority_overlay(self) -> str | None:
        overlay = resolve_authority_overlay(
            getattr(self._config.gateway, "authority_overlay", None),
            getattr(self._config.gateway, "authority_overlay_started_at", None),
        )
        return None if overlay.mode is None else overlay.mode.value
