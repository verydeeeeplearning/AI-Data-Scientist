"""Tests for shared runtime provider/auth factory."""

from __future__ import annotations

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from ds_agent.config.schema import DSAgentConfig, OAuthConfig, ProviderConfig
from ds_agent.domain.entities.auth import AuthProfile, OAuthTokenSet
from ds_agent.infrastructure.auth.token_store import AuthProfileStore
from ds_agent.infrastructure.secrets.api_key_manager import create_api_key_manager
from ds_agent.infrastructure.secrets.secret_storage import InMemorySecretStorage
from ds_agent.runtime.provider_factory import (
    create_auth_profile_store,
    create_provider_router,
    get_provider_auth_statuses,
    get_provider_health_snapshot,
)


class TestCreateAuthProfileStore:
    def test_uses_configured_token_store_path(self, tmp_path):
        config = DSAgentConfig(
            oauth=OAuthConfig(token_store_path=str(tmp_path / "auth_profiles.json"))
        )

        store = create_auth_profile_store(config)

        assert store._path == (tmp_path / "auth_profiles.json").resolve()


class TestCreateProviderRouter:
    def test_passes_configured_api_keys_fallbacks_and_token_store(self):
        config = DSAgentConfig(
            provider=ProviderConfig(
                fallback_models=["openai/gpt-4.1"],
            )
        )
        token_store = MagicMock()
        mock_router = MagicMock()
        api_key_manager = create_api_key_manager(InMemorySecretStorage())
        api_key_manager.set("openai", "sk-test")

        with patch(
            "ds_agent.runtime.provider_factory.ProviderRouter", return_value=mock_router
        ) as mock_cls:
            provider = create_provider_router(
                "openai/gpt-5.4",
                config,
                token_store=token_store,
                api_key_manager=api_key_manager,
            )

        assert provider is mock_router
        mock_cls.assert_called_once_with(
            "openai/gpt-5.4",
            fallback_models=["openai/gpt-4.1"],
            token_store=token_store,
            api_key_resolver=ANY,
        )

    def test_get_provider_auth_statuses_uses_secure_api_key_manager(self):
        api_key_manager = create_api_key_manager(InMemorySecretStorage())
        api_key_manager.set("openai", "sk-test")

        statuses = get_provider_auth_statuses(DSAgentConfig(), api_key_manager=api_key_manager)

        assert statuses["openai"] == "active"


class TestGetProviderAuthStatuses:
    def test_gemini_oauth_store_marks_provider_active(self, tmp_path):
        store = AuthProfileStore(tmp_path / "auth_profiles.json")
        store.save(
            "google:default",
            AuthProfile(
                type="oauth",
                provider="gemini",
                oauth=OAuthTokenSet(
                    access="access",
                    refresh="refresh",
                    expires=9_999_999_999_999,
                    provider="gemini",
                ),
            ),
        )
        config = DSAgentConfig(
            oauth=OAuthConfig(token_store_path=str(tmp_path / "auth_profiles.json"))
        )

        statuses = get_provider_auth_statuses(config, token_store=store)

        assert statuses["gemini"] == "active"

    def test_codex_store_marks_provider_active_without_cli_file(self, tmp_path):
        store = AuthProfileStore(tmp_path / "auth_profiles.json")
        store.save(
            "openai-codex:default",
            AuthProfile(
                type="oauth",
                provider="codex",
                oauth=OAuthTokenSet(
                    access="access",
                    refresh="refresh",
                    expires=0,
                    provider="codex",
                ),
            ),
        )
        config = DSAgentConfig(
            oauth=OAuthConfig(token_store_path=str(tmp_path / "auth_profiles.json"))
        )

        with patch("ds_agent.runtime.provider_factory.Path.home", return_value=tmp_path):
            statuses = get_provider_auth_statuses(config, token_store=store)

        assert statuses["codex"] == "active"


class TestGetProviderHealthSnapshot:
    @pytest.mark.asyncio
    async def test_includes_ollama_runtime_health(self):
        mock_ollama = MagicMock()
        mock_ollama.is_running = AsyncMock(return_value=True)
        mock_ollama.list_models = AsyncMock(return_value=[{"name": "qwen2.5"}])

        with (
            patch(
                "ds_agent.runtime.provider_factory.get_provider_auth_statuses",
                return_value={"openai": "active", "ollama": "local"},
            ),
            patch("ds_agent.runtime.provider_factory.OllamaClient", return_value=mock_ollama),
        ):
            snapshot = await get_provider_health_snapshot(DSAgentConfig())

        openai = next(item for item in snapshot if item["id"] == "openai")
        ollama = next(item for item in snapshot if item["id"] == "ollama")
        assert openai["status"] == "ok"
        assert ollama["status"] == "ok"
        assert ollama["modelCount"] == 1
        assert ollama["latencyMs"] is not None

    @pytest.mark.asyncio
    async def test_marks_ollama_unavailable_when_runtime_is_down(self):
        mock_ollama = MagicMock()
        mock_ollama.is_running = AsyncMock(return_value=False)
        mock_ollama.list_models = AsyncMock()

        with (
            patch(
                "ds_agent.runtime.provider_factory.get_provider_auth_statuses",
                return_value={"ollama": "local"},
            ),
            patch("ds_agent.runtime.provider_factory.OllamaClient", return_value=mock_ollama),
        ):
            snapshot = await get_provider_health_snapshot(DSAgentConfig())

        ollama = next(item for item in snapshot if item["id"] == "ollama")
        assert ollama["status"] == "unavailable"
        assert ollama["modelCount"] == 0
        mock_ollama.list_models.assert_not_called()
