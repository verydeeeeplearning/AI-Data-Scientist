"""OAuth callback server — ported from OpenClaw oauth.flow.ts:waitForLocalCallback().

Starts a temporary HTTP server on localhost to receive the OAuth redirect.
Validates the state parameter and captures the authorization code.
"""

from __future__ import annotations

import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlparse

import structlog

logger = structlog.get_logger()

DEFAULT_PORT = 8085
DEFAULT_CALLBACK_PATH = "/oauth2callback"
DEFAULT_TIMEOUT_S = 300  # 5 minutes, matching OpenClaw


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth callback."""

    server: Any  # Typed as Any to access custom attributes on HTTPServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path != self.server.expected_path:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        params = parse_qs(parsed.query)

        # Check for OAuth error
        error = params.get("error", [None])[0]
        if error:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Authentication failed: {error}".encode())
            self.server.result = {"error": error}
            self.server.got_callback.set()
            return

        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]

        if not code or not state:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Missing code or state")
            self.server.result = {"error": "Missing code or state"}
            self.server.got_callback.set()
            return

        # Validate state
        if state != self.server.expected_state:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Invalid state")
            self.server.result = {"error": "OAuth state mismatch"}
            self.server.got_callback.set()
            return

        # Success
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = (
            "<!doctype html><html><head><meta charset='utf-8'/></head>"
            "<body><h2>DS Agent OAuth complete</h2>"
            "<p>You can close this window and return to DS Agent.</p></body></html>"
        )
        self.wfile.write(html.encode())
        self.server.result = {"code": code, "state": state}
        self.server.got_callback.set()

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress default HTTP server logs
        pass


class OAuthCallbackServer:
    """Temporary localhost server for OAuth redirect callback.

    Usage::

        server = OAuthCallbackServer(expected_state="abc123")
        redirect_uri = server.redirect_uri  # http://localhost:8085/oauth2callback
        # ... open browser with auth URL pointing to redirect_uri ...
        result = await server.wait_for_callback()
        # result = {"code": "...", "state": "..."} or {"error": "..."}
    """

    def __init__(
        self,
        expected_state: str,
        port: int = DEFAULT_PORT,
        path: str = DEFAULT_CALLBACK_PATH,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._expected_state = expected_state
        self._port = port
        self._path = path
        self._timeout_s = timeout_s
        self._server: HTTPServer | None = None
        self._thread: Thread | None = None

    @property
    def redirect_uri(self) -> str:
        return f"http://localhost:{self._port}{self._path}"

    async def wait_for_callback(self) -> dict[str, str]:
        """Start server, wait for callback, return result.

        Returns dict with either ``{"code": ..., "state": ...}`` on success
        or ``{"error": ...}`` on failure.

        Raises ``TimeoutError`` if no callback received within timeout.
        """
        loop = asyncio.get_event_loop()
        got_callback = asyncio.Event()

        # Create HTTP server
        httpd = HTTPServer(("localhost", self._port), _CallbackHandler)
        httpd.expected_state = self._expected_state  # type: ignore[attr-defined]
        httpd.expected_path = self._path  # type: ignore[attr-defined]
        httpd.result = None  # type: ignore[attr-defined]

        # Bridge threading.Event → asyncio.Event
        _thread_event = httpd.got_callback = type("E", (), {  # type: ignore[attr-defined]
            "set": lambda self_: loop.call_soon_threadsafe(got_callback.set),
        })()

        self._server = httpd

        # Run server in background thread
        self._thread = Thread(target=httpd.serve_forever, daemon=True)
        self._thread.start()
        logger.info("oauth_callback_server_started", port=self._port, path=self._path)

        try:
            await asyncio.wait_for(got_callback.wait(), timeout=self._timeout_s)
        except TimeoutError:
            raise TimeoutError(f"OAuth callback timeout ({self._timeout_s}s)")
        finally:
            httpd.shutdown()
            self._thread.join(timeout=5)
            self._server = None
            logger.info("oauth_callback_server_stopped")

        result: dict[str, str] = httpd.result  # type: ignore[attr-defined]
        if result is None:
            return {"error": "No result received"}
        return result
