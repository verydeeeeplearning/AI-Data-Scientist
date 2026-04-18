"""Auth domain entities — OpenClaw auth-profiles pattern.

Credential types follow OpenClaw's three-tier model:
- api_key: Static API key (no refresh)
- token: Static bearer token (no refresh)
- oauth: OAuth tokens with access/refresh/expiry (auto-refreshable)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class OAuthTokenSet:
    """OAuth credential set — mirrors OpenClaw's OAuthCredentials type."""

    access: str
    refresh: str
    expires: float  # ms since epoch (OpenClaw compatible)
    provider: str
    email: str | None = None
    account_id: str | None = None
    project_id: str | None = None
    client_id: str | None = None
    display_name: str | None = None
    managed_by: str | None = None  # "codex-cli" for externally managed

    def is_expired(self) -> bool:
        """Check if the access token has expired (with 5-min buffer)."""
        import time

        buffer_ms = 5 * 60 * 1000
        return time.time() * 1000 > self.expires - buffer_ms

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> OAuthTokenSet:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class AuthProfile:
    """Single auth profile entry — mirrors OpenClaw's AuthProfileCredential union."""

    type: Literal["api_key", "token", "oauth"]
    provider: str
    # api_key type
    key: str | None = None
    # token type
    token: str | None = None
    token_expires: float | None = None
    # oauth type
    oauth: OAuthTokenSet | None = None
    # common metadata
    email: str | None = None
    display_name: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        result: dict = {"type": self.type, "provider": self.provider}
        if self.key is not None:
            result["key"] = self.key
        if self.token is not None:
            result["token"] = self.token
        if self.token_expires is not None:
            result["token_expires"] = self.token_expires
        if self.oauth is not None:
            result["oauth"] = self.oauth.to_dict()
        if self.email is not None:
            result["email"] = self.email
        if self.display_name is not None:
            result["display_name"] = self.display_name
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: dict) -> AuthProfile:
        oauth_data = data.get("oauth")
        oauth = OAuthTokenSet.from_dict(oauth_data) if oauth_data else None
        return cls(
            type=data["type"],
            provider=data["provider"],
            key=data.get("key"),
            token=data.get("token"),
            token_expires=data.get("token_expires"),
            oauth=oauth,
            email=data.get("email"),
            display_name=data.get("display_name"),
            metadata=data.get("metadata", {}),
        )
