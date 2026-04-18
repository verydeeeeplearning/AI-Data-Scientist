"""Tests for AgentSessionRegistry — extracted from AppState (4.1.4)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ds_agent.api.agent_session_registry import AgentSessionRegistry
from ds_agent.config.schema import DSAgentConfig


@pytest.fixture
def config() -> DSAgentConfig:
    return DSAgentConfig()


@pytest.fixture
def registry(config: DSAgentConfig) -> AgentSessionRegistry:
    return AgentSessionRegistry(config)


class TestAgentSessionRegistry:
    @pytest.mark.asyncio
    async def test_create_new_agent(self, registry: AgentSessionRegistry) -> None:
        callbacks = MagicMock()
        with patch.object(registry, "_create_agent", return_value=MagicMock()) as mock_create:
            agent = await registry.get_or_create("session-1", callbacks)
            mock_create.assert_called_once_with(
                "session-1",
                callbacks,
                registry._config.provider.default_model,
                authority_mode=None,
            )
            assert agent is not None

    @pytest.mark.asyncio
    async def test_reuse_existing_agent(self, registry: AgentSessionRegistry) -> None:
        callbacks = MagicMock()
        mock_agent = MagicMock()
        with patch.object(registry, "_create_agent", return_value=mock_agent):
            agent1 = await registry.get_or_create("session-1", callbacks)
            agent2 = await registry.get_or_create("session-1", callbacks)
            assert agent1 is agent2

    @pytest.mark.asyncio
    async def test_reuse_existing_agent_rebinds_callbacks(
        self, registry: AgentSessionRegistry
    ) -> None:
        first_callbacks = MagicMock()
        second_callbacks = MagicMock()
        mock_agent = MagicMock()

        with patch.object(registry, "_create_agent", return_value=mock_agent):
            await registry.get_or_create("session-1", first_callbacks)
            await registry.get_or_create("session-1", second_callbacks)

        mock_agent.set_callbacks.assert_called_once_with(second_callbacks)

    @pytest.mark.asyncio
    async def test_different_sessions_different_agents(
        self, registry: AgentSessionRegistry
    ) -> None:
        callbacks = MagicMock()
        agents_created = []

        def make_agent(
            session_id: object,
            cb: object,
            model: object = None,
            *,
            authority_mode: object = None,
        ) -> MagicMock:
            a = MagicMock()
            agents_created.append(a)
            return a

        with patch.object(registry, "_create_agent", side_effect=make_agent):
            a1 = await registry.get_or_create("session-1", callbacks)
            a2 = await registry.get_or_create("session-2", callbacks)
            assert a1 is not a2

    def test_get_nonexistent_returns_none(self, registry: AgentSessionRegistry) -> None:
        assert registry.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_existing(self, registry: AgentSessionRegistry) -> None:
        callbacks = MagicMock()
        with patch.object(registry, "_create_agent", return_value=MagicMock()):
            await registry.get_or_create("session-1", callbacks)
            agent = registry.get("session-1")
            assert agent is not None

    @pytest.mark.asyncio
    async def test_active_count(self, registry: AgentSessionRegistry) -> None:
        callbacks = MagicMock()
        assert registry.active_count == 0
        with patch.object(registry, "_create_agent", return_value=MagicMock()):
            await registry.get_or_create("s1", callbacks)
            assert registry.active_count == 1
            await registry.get_or_create("s2", callbacks)
            assert registry.active_count == 2

    @pytest.mark.asyncio
    async def test_replaces_agent_when_model_changes(self, registry: AgentSessionRegistry) -> None:
        callbacks = MagicMock()
        first_agent = MagicMock()
        second_agent = MagicMock()

        with patch.object(registry, "_create_agent", side_effect=[first_agent, second_agent]):
            agent1 = await registry.get_or_create("session-1", callbacks, model="openai/gpt-4.1")
            agent2 = await registry.get_or_create(
                "session-1",
                callbacks,
                model="anthropic/claude-sonnet-4-6",
            )

        assert agent1 is first_agent
        assert agent2 is second_agent
        assert registry.active_count == 1

    @pytest.mark.asyncio
    async def test_replaces_agent_when_authority_overlay_changes(
        self, registry: AgentSessionRegistry
    ) -> None:
        callbacks = MagicMock()
        first_agent = MagicMock()
        second_agent = MagicMock()

        with patch.object(registry, "_create_agent", side_effect=[first_agent, second_agent]):
            agent1 = await registry.get_or_create("session-1", callbacks)
            registry._config.gateway.authority_overlay = "freeze"
            agent2 = await registry.get_or_create("session-1", callbacks)

        assert agent1 is first_agent
        assert agent2 is second_agent
        assert registry.active_count == 1

    @pytest.mark.asyncio
    async def test_reuses_existing_agent_when_model_is_omitted(
        self, registry: AgentSessionRegistry
    ) -> None:
        callbacks = MagicMock()
        mock_agent = MagicMock()

        with patch.object(registry, "_create_agent", return_value=mock_agent) as mock_create:
            agent1 = await registry.get_or_create("session-1", callbacks, model="openai/gpt-4.1")
            agent2 = await registry.get_or_create("session-1", callbacks)

        assert agent1 is agent2
        assert mock_create.call_count == 1

    def test_get_status(self, registry: AgentSessionRegistry) -> None:
        status = registry.get_status()
        assert "model" in status
        assert "qualityPreset" in status
        assert "mode" in status
        assert status["qualityPreset"] == "balanced"
        assert status["activeSessions"] == 0

    def test_create_agent_passes_use_case_context(self, registry: AgentSessionRegistry) -> None:
        registry._config.agent.use_case_hint = "reporting"
        registry._config.agent.use_case_context = "Favor concise decision-ready summaries."
        callbacks = MagicMock()
        mock_provider = MagicMock()

        with (
            patch(
                "ds_agent.runtime.provider_factory.create_provider_router",
                return_value=mock_provider,
            ),
            patch("ds_agent.agent.factory.create_agent", return_value=MagicMock()) as mock_create,
        ):
            registry._create_agent("session-1", callbacks)

        assert mock_create.call_args.kwargs["use_case_hint"] == "reporting"
        assert (
            mock_create.call_args.kwargs["use_case_context"]
            == "Favor concise decision-ready summaries."
        )

    def test_create_agent_passes_effective_authority_overlay(
        self, registry: AgentSessionRegistry
    ) -> None:
        callbacks = MagicMock()
        mock_provider = MagicMock()

        with (
            patch(
                "ds_agent.runtime.provider_factory.create_provider_router",
                return_value=mock_provider,
            ),
            patch("ds_agent.agent.factory.create_agent", return_value=MagicMock()) as mock_create,
        ):
            registry._create_agent("session-1", callbacks, authority_mode="freeze")

        assert mock_create.call_args.kwargs["authority_mode"] == "freeze"

    def test_create_agent_wires_provider_events_to_session_context(
        self, registry: AgentSessionRegistry
    ) -> None:
        callbacks = MagicMock()
        mock_provider = MagicMock()

        with (
            patch(
                "ds_agent.runtime.provider_factory.create_provider_router",
                return_value=mock_provider,
            ) as mock_router,
            patch("ds_agent.agent.factory.create_agent", return_value=MagicMock()),
        ):
            registry._create_agent("session-42", callbacks)

        emit_event = mock_router.call_args.kwargs["emit_event"]
        assert callable(emit_event)

        emit_event(
            "provider.fallback",
            {"from": "anthropic/claude-opus-4-6", "to": "openai/gpt-4.1"},
        )

        callbacks.emit_event.assert_called_once_with(
            "provider.fallback",
            {
                "sessionId": "session-42",
                "surface": "ws",
                "from": "anthropic/claude-opus-4-6",
                "to": "openai/gpt-4.1",
            },
        )
