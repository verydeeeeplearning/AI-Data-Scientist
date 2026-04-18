"""OAuth service — Gemini PKCE flow + Codex CLI delegation.

Ported from OpenClaw patterns:
- extensions/google/oauth.flow.ts (PKCE + callback server)
- extensions/google/oauth.token.ts (token exchange)
- extensions/google/oauth.shared.ts (constants)
- extensions/openai/openai-codex-cli-auth.ts (Codex CLI credential reading)
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

import structlog

from ds_agent.domain.entities.auth import AuthProfile, OAuthTokenSet
from ds_agent.infrastructure.auth.callback_server import OAuthCallbackServer
from ds_agent.infrastructure.auth.pkce import (
    build_auth_url,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
)
from ds_agent.infrastructure.auth.token_store import AuthProfileStore

logger = structlog.get_logger()

# -- Google OAuth constants (from OpenClaw oauth.shared.ts) --------------------

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo?alt=json"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
GOOGLE_REDIRECT_PORT = 8085
GOOGLE_REDIRECT_PATH = "/oauth2callback"

# -- Codex constants -----------------------------------------------------------

CODEX_AUTH_FILE = Path.home() / ".codex" / "auth.json"

# -- Token exchange timeout ----------------------------------------------------

HTTP_TIMEOUT_S = 10


class OAuthService:
    """Orchestrates OAuth login flows for Gemini and Codex."""

    def __init__(
        self,
        store: AuthProfileStore,
        gemini_client_id: str = "",
        gemini_client_secret: str = "",
    ) -> None:
        self._store = store
        self._gemini_client_id = gemini_client_id
        self._gemini_client_secret = gemini_client_secret
        self._pending_login: dict[str, asyncio.Task] = {}  # type: ignore[type-arg]

    # -- Gemini PKCE flow ------------------------------------------------------

    async def start_gemini_login(self) -> dict[str, str]:
        """Start Gemini OAuth PKCE flow.

        Opens the system browser for Google consent screen.
        Returns ``{"auth_url": "...", "provider": "gemini"}`` immediately.
        The actual token exchange happens asynchronously; call
        ``await wait_for_login("gemini")`` to get the result.
        """
        if not self._gemini_client_id:
            raise ValueError("gemini_client_id not configured")

        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)
        state = generate_state()

        redirect_uri = f"http://localhost:{GOOGLE_REDIRECT_PORT}{GOOGLE_REDIRECT_PATH}"
        auth_url = build_auth_url(
            auth_endpoint=GOOGLE_AUTH_URL,
            client_id=self._gemini_client_id,
            redirect_uri=redirect_uri,
            scopes=GOOGLE_SCOPES,
            code_challenge=challenge,
            state=state,
        )

        # Start background task for callback + token exchange
        task = asyncio.create_task(
            self._gemini_callback_flow(state, verifier, redirect_uri)
        )
        self._pending_login["gemini"] = task

        # Open browser
        webbrowser.open(auth_url)
        logger.info("gemini_oauth_started", auth_url=auth_url[:80] + "...")

        return {"auth_url": auth_url, "provider": "gemini"}

    async def _gemini_callback_flow(
        self, state: str, verifier: str, redirect_uri: str
    ) -> OAuthTokenSet:
        """Wait for callback, exchange code for tokens, save to store."""
        server = OAuthCallbackServer(
            expected_state=state,
            port=GOOGLE_REDIRECT_PORT,
            path=GOOGLE_REDIRECT_PATH,
        )
        result = await server.wait_for_callback()

        if "error" in result:
            raise RuntimeError(f"Gemini OAuth failed: {result['error']}")

        code = result["code"]
        tokens = await self._exchange_google_code(code, verifier, redirect_uri)

        # Save to store
        profile = AuthProfile(
            type="oauth",
            provider="gemini",
            oauth=tokens,
            email=tokens.email,
        )
        self._store.save("google:default", profile)
        logger.info("gemini_oauth_complete", email=tokens.email)

        return tokens

    async def _exchange_google_code(
        self, code: str, verifier: str, redirect_uri: str
    ) -> OAuthTokenSet:
        """Exchange authorization code for tokens (OpenClaw oauth.token.ts pattern)."""
        body = urllib.parse.urlencode({
            "client_id": self._gemini_client_id,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
            **({"client_secret": self._gemini_client_secret}
               if self._gemini_client_secret else {}),
        }).encode()

        data = await asyncio.to_thread(self._http_post, GOOGLE_TOKEN_URL, body)

        if "error" in data:
            raise RuntimeError(f"Token exchange failed: {data.get('error_description', data['error'])}")

        access_token = data["access_token"]
        refresh_token = data.get("refresh_token", "")
        expires_in = data.get("expires_in", 3600)

        # Fetch user info
        email = await self._fetch_google_email(access_token)

        # OpenClaw pattern: expires = now + expires_in - 5min buffer
        expires_at = time.time() * 1000 + expires_in * 1000 - 5 * 60 * 1000

        return OAuthTokenSet(
            access=access_token,
            refresh=refresh_token,
            expires=expires_at,
            provider="gemini",
            email=email,
            client_id=self._gemini_client_id,
        )

    async def _fetch_google_email(self, access_token: str) -> str | None:
        """Fetch user email from Google userinfo endpoint."""
        try:
            req = urllib.request.Request(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            data = await asyncio.to_thread(self._http_get_json, req)
            return data.get("email")
        except Exception as e:
            logger.warning("google_userinfo_failed", error=str(e))
            return None

    # -- Gemini token refresh --------------------------------------------------

    async def refresh_gemini_token(self) -> OAuthTokenSet:
        """Refresh expired Gemini access token using refresh_token."""
        profile = self._store.load_by_provider("gemini")
        if not profile or not profile.oauth:
            raise RuntimeError("No Gemini OAuth credentials found")

        old = profile.oauth
        body = urllib.parse.urlencode({
            "client_id": old.client_id or self._gemini_client_id,
            "refresh_token": old.refresh,
            "grant_type": "refresh_token",
            **({"client_secret": self._gemini_client_secret}
               if self._gemini_client_secret else {}),
        }).encode()

        data = await asyncio.to_thread(self._http_post, GOOGLE_TOKEN_URL, body)

        if "error" in data:
            raise RuntimeError(f"Token refresh failed: {data.get('error_description', data['error'])}")

        new_access = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        expires_at = time.time() * 1000 + expires_in * 1000 - 5 * 60 * 1000

        updated = OAuthTokenSet(
            access=new_access,
            refresh=data.get("refresh_token", old.refresh),
            expires=expires_at,
            provider="gemini",
            email=old.email,
            client_id=old.client_id,
            project_id=old.project_id,
        )

        profile.oauth = updated
        self._store.save("google:default", profile)
        logger.info("gemini_token_refreshed", email=old.email)

        return updated

    # -- Codex CLI delegation --------------------------------------------------

    async def start_codex_login(self) -> OAuthTokenSet:
        """Start Codex login by delegating to ``codex login`` CLI.

        If ``~/.codex/auth.json`` already exists, reads it directly.
        Otherwise runs ``codex login`` and waits for the file to appear.
        """
        # Check existing credentials first
        existing = self._read_codex_auth_file()
        if existing:
            self._save_codex_profile(existing)
            return existing

        # Run codex login
        logger.info("codex_login_starting", message="Running 'codex login'...")
        try:
            proc = await asyncio.to_thread(
                subprocess.Popen,
                ["codex", "login"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "Codex CLI not found. Install it first:\n"
                "  npm install -g @openai/codex\n"
                "Then try again."
            )

        # Poll for auth.json (up to 5 minutes)
        for _ in range(300):
            await asyncio.sleep(1)
            tokens = self._read_codex_auth_file()
            if tokens:
                proc.terminate()
                self._save_codex_profile(tokens)
                return tokens

        proc.terminate()
        raise TimeoutError("Codex login timed out (5 minutes)")

    def _read_codex_auth_file(self, path: Path | None = None) -> OAuthTokenSet | None:
        """Read Codex credentials from ``~/.codex/auth.json``.

        Expected format (from OpenClaw codex-cli-auth.ts)::

            {"auth_mode": "chatgpt", "tokens": {"access_token": "...", "refresh_token": "...", "account_id": "..."}}
        """
        auth_path = path or CODEX_AUTH_FILE
        if not auth_path.exists():
            return None

        try:
            data = json.loads(auth_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        if data.get("auth_mode") != "chatgpt":
            return None

        tokens = data.get("tokens", {})
        access = tokens.get("access_token")
        if not access:
            return None

        return OAuthTokenSet(
            access=access,
            refresh=tokens.get("refresh_token", ""),
            expires=0,  # Codex CLI doesn't expose expiry
            provider="codex",
            account_id=tokens.get("account_id"),
            managed_by="codex-cli",
        )

    def _save_codex_profile(self, tokens: OAuthTokenSet) -> None:
        profile = AuthProfile(
            type="oauth",
            provider="codex",
            oauth=tokens,
        )
        self._store.save("openai-codex:codex-cli", profile)
        logger.info("codex_oauth_saved", managed_by="codex-cli")

    # -- Status & disconnect ---------------------------------------------------

    def get_status(self, provider: str) -> dict[str, Any]:
        """Get auth status for a provider."""
        profile = self._store.load_by_provider(provider)

        if provider == "codex" and not profile:
            # Also check Codex CLI file directly
            tokens = self._read_codex_auth_file()
            if tokens:
                self._save_codex_profile(tokens)
                return {
                    "authenticated": True,
                    "email": None,
                    "account_id": tokens.account_id,
                    "managed_by": "codex-cli",
                    "expires_at": None,
                }

        if not profile or not profile.oauth:
            return {"authenticated": False}

        oauth = profile.oauth
        return {
            "authenticated": True,
            "email": oauth.email,
            "account_id": oauth.account_id,
            "managed_by": oauth.managed_by,
            "expires_at": oauth.expires if oauth.expires > 0 else None,
            "expired": oauth.is_expired() if oauth.expires > 0 else False,
        }

    def disconnect(self, provider: str) -> None:
        """Remove all auth profiles for a provider."""
        self._store.delete_by_provider(provider)
        logger.info("oauth_disconnected", provider=provider)

    async def wait_for_login(self, provider: str) -> OAuthTokenSet:
        """Wait for a pending login to complete."""
        task = self._pending_login.get(provider)
        if not task:
            raise RuntimeError(f"No pending login for {provider}")
        try:
            result: OAuthTokenSet = await task
            return result
        finally:
            self._pending_login.pop(provider, None)

    # -- HTTP helpers ----------------------------------------------------------

    @staticmethod
    def _http_post(url: str, body: bytes) -> dict:
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            payload: dict = json.loads(resp.read())
            return payload

    @staticmethod
    def _http_get_json(req: urllib.request.Request) -> dict:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            payload: dict = json.loads(resp.read())
            return payload
