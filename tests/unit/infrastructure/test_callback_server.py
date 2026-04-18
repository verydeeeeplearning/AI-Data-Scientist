"""Tests for OAuth callback server."""

from __future__ import annotations

import asyncio

import pytest
import urllib.request

from ds_agent.infrastructure.auth.callback_server import OAuthCallbackServer


@pytest.fixture
def make_server():
    """Factory for callback servers on ephemeral ports."""
    servers = []

    def _make(state: str, port: int = 0, timeout_s: float = 10):
        # Use port 0 to let OS pick an available port for tests
        s = OAuthCallbackServer(expected_state=state, port=port, timeout_s=timeout_s)
        servers.append(s)
        return s

    yield _make


class TestCallbackServer:
    async def test_successful_callback(self, make_server, unused_tcp_port):
        state = "test-state-123"
        server = OAuthCallbackServer(
            expected_state=state, port=unused_tcp_port, timeout_s=10,
        )

        async def send_callback():
            await asyncio.sleep(0.3)
            url = f"http://localhost:{unused_tcp_port}/oauth2callback?code=auth-code-xyz&state={state}"
            await asyncio.to_thread(urllib.request.urlopen, url)

        task = asyncio.create_task(send_callback())
        result = await server.wait_for_callback()
        await task

        assert result["code"] == "auth-code-xyz"
        assert result["state"] == state

    async def test_state_mismatch(self, unused_tcp_port):
        server = OAuthCallbackServer(
            expected_state="correct-state", port=unused_tcp_port, timeout_s=10,
        )

        async def send_bad_callback():
            await asyncio.sleep(0.3)
            url = f"http://localhost:{unused_tcp_port}/oauth2callback?code=abc&state=wrong-state"
            try:
                await asyncio.to_thread(urllib.request.urlopen, url)
            except urllib.error.HTTPError:
                pass  # Expected 400

        task = asyncio.create_task(send_bad_callback())
        result = await server.wait_for_callback()
        await task

        assert "error" in result
        assert "mismatch" in result["error"]

    async def test_oauth_error_parameter(self, unused_tcp_port):
        server = OAuthCallbackServer(
            expected_state="some-state", port=unused_tcp_port, timeout_s=10,
        )

        async def send_error_callback():
            await asyncio.sleep(0.3)
            url = f"http://localhost:{unused_tcp_port}/oauth2callback?error=access_denied"
            try:
                await asyncio.to_thread(urllib.request.urlopen, url)
            except urllib.error.HTTPError:
                pass

        task = asyncio.create_task(send_error_callback())
        result = await server.wait_for_callback()
        await task

        assert result["error"] == "access_denied"

    async def test_timeout(self, unused_tcp_port):
        server = OAuthCallbackServer(
            expected_state="s", port=unused_tcp_port, timeout_s=0.5,
        )
        with pytest.raises(TimeoutError, match="timeout"):
            await server.wait_for_callback()

    async def test_missing_code(self, unused_tcp_port):
        server = OAuthCallbackServer(
            expected_state="s", port=unused_tcp_port, timeout_s=10,
        )

        async def send_incomplete():
            await asyncio.sleep(0.3)
            url = f"http://localhost:{unused_tcp_port}/oauth2callback?state=s"
            try:
                await asyncio.to_thread(urllib.request.urlopen, url)
            except urllib.error.HTTPError:
                pass

        task = asyncio.create_task(send_incomplete())
        result = await server.wait_for_callback()
        await task

        assert "error" in result

    def test_redirect_uri_format(self):
        server = OAuthCallbackServer(expected_state="s", port=9999)
        assert server.redirect_uri == "http://localhost:9999/oauth2callback"


@pytest.fixture
def unused_tcp_port():
    """Find an unused TCP port."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]
