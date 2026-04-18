"""PKCE utilities — ported from OpenClaw extensions/google/oauth.flow.ts.

Implements Proof Key for Code Exchange (RFC 7636) for OAuth 2.0 desktop flows.
Uses SHA-256 challenge method (S256) matching OpenClaw's implementation.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode


def generate_code_verifier() -> str:
    """Generate a random PKCE code verifier (64 hex chars = 32 bytes).

    Matches OpenClaw: ``randomBytes(32).toString("hex")``
    """
    return secrets.token_hex(32)


def generate_code_challenge(verifier: str) -> str:
    """Derive S256 code challenge from verifier.

    Matches OpenClaw: ``createHash("sha256").update(verifier).digest("base64url")``
    """
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_state() -> str:
    """Generate a random state parameter for CSRF protection.

    Matches OpenClaw: ``randomBytes(32).toString("hex")``
    """
    return secrets.token_hex(32)


def build_auth_url(
    auth_endpoint: str,
    client_id: str,
    redirect_uri: str,
    scopes: list[str],
    code_challenge: str,
    state: str,
    *,
    access_type: str = "offline",
    prompt: str = "consent",
) -> str:
    """Build the OAuth authorization URL with PKCE parameters.

    Matches OpenClaw's ``buildAuthUrl()`` in oauth.flow.ts.
    """
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "access_type": access_type,
        "prompt": prompt,
    }
    return f"{auth_endpoint}?{urlencode(params)}"
