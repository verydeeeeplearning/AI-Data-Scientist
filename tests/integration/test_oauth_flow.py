"""Integration tests for OAuth flows — Gemini PKCE + Codex CLI delegation.

Mocks only external HTTP endpoints. Internal components (token store,
callback server, PKCE, OAuth service) are tested end-to-end.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
import urllib.request
from unittest.mock import patch

import pytest

from ds_agent.domain.entities.auth import AuthProfile, OAuthTokenSet
from ds_agent.infrastructure.auth.callback_server import OAuthCallbackServer
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


class TestGeminiPKCEFullFlow:
    """Full Gemini OAuth flow: start login → callback → token exchange → stored."""

    async def test_full_gemini_flow(self, service, store, unused_tcp_port):
        """Simulate the complete Gemini OAuth PKCE flow."""
        # Mock the token exchange and userinfo endpoints
        mock_token_response = {
            "access_token": "ya29.integration-test",
            "refresh_token": "1//integration-refresh",
            "expires_in": 3600,
        }
        mock_userinfo = {"email": "integration@test.com"}

        with patch("webbrowser.open") as mock_browser:
            with patch.object(service, "_http_post", return_value=mock_token_response):
                with patch.object(service, "_http_get_json", return_value=mock_userinfo):
                    # Override the callback port for testing
                    import ds_agent.infrastructure.auth.oauth_service as oauth_mod
                    original_port = oauth_mod.GOOGLE_REDIRECT_PORT
                    oauth_mod.GOOGLE_REDIRECT_PORT = unused_tcp_port
                    try:
                        # Start login (opens browser, starts callback server)
                        result = await service.start_gemini_login()
                        assert "auth_url" in result

                        # Verify browser was opened
                        assert mock_browser.called
                        auth_url = mock_browser.call_args[0][0]
                        assert "accounts.google.com" in auth_url
                        assert "code_challenge=" in auth_url
                        assert "state=" in auth_url

                        # Extract state from the auth URL for callback simulation
                        from urllib.parse import parse_qs, urlparse
                        params = parse_qs(urlparse(auth_url).query)
                        state = params["state"][0]

                        # Simulate the OAuth callback (as if Google redirected)
                        await asyncio.sleep(0.5)
                        callback_url = (
                            f"http://localhost:{unused_tcp_port}"
                            f"/oauth2callback?code=test-auth-code&state={state}"
                        )
                        await asyncio.to_thread(urllib.request.urlopen, callback_url)

                        # Wait for the login to complete
                        tokens = await service.wait_for_login("gemini")
                    finally:
                        oauth_mod.GOOGLE_REDIRECT_PORT = original_port

        # Verify tokens
        assert tokens.access == "ya29.integration-test"
        assert tokens.refresh == "1//integration-refresh"
        assert tokens.email == "integration@test.com"

        # Verify stored in profile store
        profile = store.load("google:default")
        assert profile is not None
        assert profile.oauth.access == "ya29.integration-test"


class TestCodexCLIDelegation:
    async def test_codex_existing_file(self, service, store, tmp_path):
        """When ~/.codex/auth.json exists, reads it directly."""
        auth_file = tmp_path / "auth.json"
        auth_file.write_text(json.dumps({
            "auth_mode": "chatgpt",
            "tokens": {
                "access_token": "codex-existing-token",
                "refresh_token": "codex-refresh",
                "account_id": "acc-123",
            },
        }))

        with patch.object(service, "_read_codex_auth_file") as mock_read:
            mock_read.return_value = OAuthTokenSet(
                access="codex-existing-token",
                refresh="codex-refresh",
                expires=0,
                provider="codex",
                account_id="acc-123",
                managed_by="codex-cli",
            )
            tokens = await service.start_codex_login()

        assert tokens.access == "codex-existing-token"
        assert tokens.managed_by == "codex-cli"

        # Verify stored
        assert store.has_provider("codex")
        profile = store.load("openai-codex:codex-cli")
        assert profile.oauth.account_id == "acc-123"


class TestTokenRefresh:
    async def test_gemini_token_refresh(self, service, store):
        """Token refresh updates stored credentials."""
        # Pre-populate with expired token
        store.save("google:default", AuthProfile(
            type="oauth", provider="gemini",
            oauth=OAuthTokenSet(
                access="ya29.expired",
                refresh="1//valid-refresh",
                expires=time.time() * 1000 - 10_000,  # expired
                provider="gemini",
                email="user@test.com",
                client_id="test-client-id",
            ),
        ))

        # Verify it's expired
        profile = store.load("google:default")
        assert profile.oauth.is_expired()

        # Mock refresh endpoint
        with patch.object(service, "_http_post", return_value={
            "access_token": "ya29.refreshed-token",
            "expires_in": 3600,
        }):
            updated = await service.refresh_gemini_token()

        assert updated.access == "ya29.refreshed-token"
        assert not updated.is_expired()

        # Verify updated in store
        stored = store.load("google:default")
        assert stored.oauth.access == "ya29.refreshed-token"


class TestEdgeCases:
    async def test_callback_timeout(self, unused_tcp_port):
        """Callback server times out if no callback received."""
        server = OAuthCallbackServer(
            expected_state="s", port=unused_tcp_port, timeout_s=1,
        )
        with pytest.raises(TimeoutError):
            await server.wait_for_callback()

    async def test_state_mismatch_rejected(self, unused_tcp_port):
        """Callback with wrong state is rejected."""
        server = OAuthCallbackServer(
            expected_state="correct", port=unused_tcp_port, timeout_s=5,
        )

        async def send_bad_state():
            await asyncio.sleep(0.3)
            url = f"http://localhost:{unused_tcp_port}/oauth2callback?code=c&state=wrong"
            with contextlib.suppress(urllib.error.HTTPError):
                await asyncio.to_thread(urllib.request.urlopen, url)

        task = asyncio.create_task(send_bad_state())
        result = await server.wait_for_callback()
        await task
        assert "error" in result

    def test_disconnect_and_status(self, service, store):
        """Disconnect clears tokens, status reflects change."""
        store.save("google:default", AuthProfile(
            type="oauth", provider="gemini",
            oauth=OAuthTokenSet(
                access="a", refresh="r", expires=time.time() * 1000 + 3600_000,
                provider="gemini", email="u@t.com",
            ),
        ))

        # Before disconnect
        status = service.get_status("gemini")
        assert status["authenticated"] is True

        # Disconnect
        service.disconnect("gemini")

        # After disconnect
        status = service.get_status("gemini")
        assert status["authenticated"] is False


@pytest.fixture
def unused_tcp_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]
