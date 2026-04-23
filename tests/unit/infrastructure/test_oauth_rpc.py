"""Tests for OAuth RPC methods in WsRpcHandler."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from ds_agent.domain.entities.auth import AuthProfile, OAuthTokenSet
from ds_agent.infrastructure.auth.oauth_service import OAuthService
from ds_agent.infrastructure.auth.token_store import AuthProfileStore


@pytest.fixture
def store(tmp_path):
    return AuthProfileStore(tmp_path / "auth_profiles.json")


@pytest.fixture
def service(store):
    return OAuthService(
        store=store,
        gemini_client_id="test-client-id",
        gemini_client_secret="test-secret",
    )


class TestOAuthServiceRPCContract:
    """Test that the OAuthService methods match what RPC handlers call."""

    async def test_gemini_start_login_returns_auth_url(self, service):
        with patch("webbrowser.open"):
            with patch.object(service, "_gemini_callback_flow", new_callable=AsyncMock):
                result = await service.start_gemini_login()

        assert "auth_url" in result
        assert result["provider"] == "gemini"
        assert "client_id=test-client-id" in result["auth_url"]
        assert "code_challenge=" in result["auth_url"]
        assert "state=" in result["auth_url"]

    def test_get_status_gemini_not_configured(self, service):
        status = service.get_status("gemini")
        assert status == {"authenticated": False}

    def test_get_status_gemini_authenticated(self, service, store):
        store.save("google:default", AuthProfile(
            type="oauth", provider="gemini",
            oauth=OAuthTokenSet(
                access="ya29.test", refresh="1//ref",
                expires=time.time() * 1000 + 3600_000,
                provider="gemini", email="test@gmail.com",
            ),
        ))
        status = service.get_status("gemini")
        assert status["authenticated"] is True
        assert status["email"] == "test@gmail.com"
        assert status["expired"] is False

    def test_get_status_codex_not_configured(self, service):
        with patch.object(service, "_read_codex_auth_file", return_value=None):
            status = service.get_status("codex")
        assert status == {"authenticated": False}

    def test_disconnect_clears_store(self, service, store):
        store.save("google:default", AuthProfile(
            type="oauth", provider="gemini",
            oauth=OAuthTokenSet(
                access="a", refresh="r", expires=0, provider="gemini",
            ),
        ))
        assert store.has_provider("gemini")
        service.disconnect("gemini")
        assert not store.has_provider("gemini")

    async def test_codex_login_with_existing_file(self, service, store, tmp_path):
        tokens = OAuthTokenSet(
            access="codex-tok", refresh="r", expires=0,
            provider="codex", managed_by="codex-cli",
        )
        with patch.object(service, "_read_codex_auth_file", return_value=tokens):
            result = await service.start_codex_login()

        assert result.access == "codex-tok"
        assert store.has_provider("codex")

    async def test_gemini_refresh_token(self, service, store):
        store.save("google:default", AuthProfile(
            type="oauth", provider="gemini",
            oauth=OAuthTokenSet(
                access="old", refresh="1//ref",
                expires=0, provider="gemini",
                email="u@test.com", client_id="test-client-id",
            ),
        ))

        with patch.object(service, "_http_post", return_value={
            "access_token": "ya29.fresh",
            "expires_in": 3600,
        }):
            updated = await service.refresh_gemini_token()

        assert updated.access == "ya29.fresh"
        assert updated.refresh == "1//ref"

    async def test_wait_for_login_no_pending(self, service):
        with pytest.raises(RuntimeError, match="No pending login"):
            await service.wait_for_login("gemini")
