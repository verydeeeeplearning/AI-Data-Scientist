"""Tests for OAuthService — Gemini PKCE mock + Codex CLI delegation."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from ds_agent.domain.entities.auth import OAuthTokenSet
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


# -- Codex CLI delegation -----------------------------------------------------


class TestCodexAuth:
    def test_read_codex_auth_file(self, service, tmp_path):
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({
            "auth_mode": "chatgpt",
            "tokens": {
                "access_token": "codex-access-123",
                "refresh_token": "codex-refresh-456",
                "account_id": "acc-789",
            },
        }))

        tokens = service._read_codex_auth_file(auth_file)
        assert tokens is not None
        assert tokens.access == "codex-access-123"
        assert tokens.refresh == "codex-refresh-456"
        assert tokens.account_id == "acc-789"
        assert tokens.managed_by == "codex-cli"

    def test_read_codex_auth_file_missing(self, service, tmp_path):
        assert service._read_codex_auth_file(tmp_path / "nonexistent.json") is None

    def test_read_codex_auth_file_invalid_mode(self, service, tmp_path):
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({
            "auth_mode": "api-key",
            "tokens": {"access_token": "x"},
        }))
        assert service._read_codex_auth_file(auth_file) is None

    def test_read_codex_auth_file_no_access_token(self, service, tmp_path):
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({
            "auth_mode": "chatgpt",
            "tokens": {"refresh_token": "r"},
        }))
        assert service._read_codex_auth_file(auth_file) is None

    def test_read_codex_auth_file_corrupted(self, service, tmp_path):
        auth_file = tmp_path / "auth.json"
        auth_file.write_text("{bad json")
        assert service._read_codex_auth_file(auth_file) is None

    async def test_start_codex_login_existing_file(self, service, store, tmp_path):
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({
            "auth_mode": "chatgpt",
            "tokens": {"access_token": "existing-tok", "refresh_token": "r"},
        }))

        with patch.object(service, "_read_codex_auth_file", side_effect=[
            OAuthTokenSet(
                access="existing-tok", refresh="r", expires=0,
                provider="codex", managed_by="codex-cli",
            ),
        ]):
            tokens = await service.start_codex_login()

        assert tokens.access == "existing-tok"
        assert store.has_provider("codex")

    async def test_start_codex_login_cli_not_found(self, service):
        with patch.object(service, "_read_codex_auth_file", return_value=None):
            with pytest.raises(RuntimeError, match="Codex CLI not found"):
                await service.start_codex_login()


# -- Gemini PKCE flow (mocked) ------------------------------------------------


class TestGeminiAuth:
    async def test_start_gemini_login_returns_url(self, service):
        with patch("webbrowser.open"):
            with patch.object(service, "_gemini_callback_flow", new_callable=AsyncMock):
                result = await service.start_gemini_login()

        assert "auth_url" in result
        assert "accounts.google.com" in result["auth_url"]
        assert result["provider"] == "gemini"

    async def test_start_gemini_login_no_client_id(self, store):
        service = OAuthService(store=store, gemini_client_id="")
        with pytest.raises(ValueError, match="gemini_client_id"):
            await service.start_gemini_login()

    async def test_exchange_google_code(self, service):
        mock_token_response = {
            "access_token": "ya29.new-access",
            "refresh_token": "1//new-refresh",
            "expires_in": 3600,
        }
        mock_userinfo = {"email": "user@gmail.com"}

        with patch.object(service, "_http_post", return_value=mock_token_response):
            with patch.object(service, "_http_get_json", return_value=mock_userinfo):
                tokens = await service._exchange_google_code(
                    code="auth-code",
                    verifier="test-verifier",
                    redirect_uri="http://localhost:8085/oauth2callback",
                )

        assert tokens.access == "ya29.new-access"
        assert tokens.refresh == "1//new-refresh"
        assert tokens.email == "user@gmail.com"
        assert tokens.provider == "gemini"
        assert tokens.expires > time.time() * 1000  # future

    async def test_exchange_google_code_error(self, service):
        with patch.object(service, "_http_post", return_value={
            "error": "invalid_grant",
            "error_description": "Code has expired",
        }), pytest.raises(RuntimeError, match="Code has expired"):
            await service._exchange_google_code("bad-code", "v", "http://x")

    async def test_refresh_gemini_token(self, service, store):
        # Pre-populate store with existing tokens
        from ds_agent.domain.entities.auth import AuthProfile
        store.save("google:default", AuthProfile(
            type="oauth", provider="gemini",
            oauth=OAuthTokenSet(
                access="old-access", refresh="1//old-refresh",
                expires=0, provider="gemini",
                email="user@test.com", client_id="test-client-id",
            ),
        ))

        mock_refresh_response = {
            "access_token": "ya29.refreshed",
            "expires_in": 3600,
        }

        with patch.object(service, "_http_post", return_value=mock_refresh_response):
            updated = await service.refresh_gemini_token()

        assert updated.access == "ya29.refreshed"
        assert updated.refresh == "1//old-refresh"  # keeps old refresh token
        assert updated.email == "user@test.com"

        # Verify persisted
        saved = store.load("google:default")
        assert saved.oauth.access == "ya29.refreshed"

    async def test_refresh_gemini_token_no_credentials(self, service):
        with pytest.raises(RuntimeError, match="No Gemini OAuth credentials"):
            await service.refresh_gemini_token()


# -- Status & disconnect -------------------------------------------------------


class TestStatusAndDisconnect:
    def test_get_status_authenticated(self, service, store):
        from ds_agent.domain.entities.auth import AuthProfile
        store.save("google:default", AuthProfile(
            type="oauth", provider="gemini",
            oauth=OAuthTokenSet(
                access="a", refresh="r",
                expires=time.time() * 1000 + 3600_000,
                provider="gemini", email="user@test.com",
            ),
        ))

        status = service.get_status("gemini")
        assert status["authenticated"] is True
        assert status["email"] == "user@test.com"
        assert status["expired"] is False

    def test_get_status_not_authenticated(self, service):
        status = service.get_status("gemini")
        assert status["authenticated"] is False

    def test_get_status_codex_from_file(self, service, tmp_path):
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({
            "auth_mode": "chatgpt",
            "tokens": {"access_token": "tok", "refresh_token": "r", "account_id": "acc"},
        }))

        with patch.object(service, "_read_codex_auth_file", return_value=OAuthTokenSet(
            access="tok", refresh="r", expires=0,
            provider="codex", account_id="acc", managed_by="codex-cli",
        )):
            status = service.get_status("codex")

        assert status["authenticated"] is True
        assert status["managed_by"] == "codex-cli"

    def test_disconnect(self, service, store):
        from ds_agent.domain.entities.auth import AuthProfile
        store.save("google:default", AuthProfile(
            type="oauth", provider="gemini",
            oauth=OAuthTokenSet(
                access="a", refresh="r", expires=0, provider="gemini",
            ),
        ))

        service.disconnect("gemini")
        assert not store.has_provider("gemini")
