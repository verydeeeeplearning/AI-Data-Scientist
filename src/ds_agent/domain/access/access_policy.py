from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Final, Literal

from .viewer_role import ViewerRole

AccessAction = Literal["view", "mutate", "export", "share"]

_PUBLIC_LINK_TOKEN_BYTES: Final[int] = 32
_PUBLIC_LINK_TTL_SECONDS: Final[int] = 7 * 24 * 60 * 60  # 7 days

_PERMISSION_MATRIX: Final[dict[ViewerRole, frozenset[AccessAction]]] = {
    "owner": frozenset({"view", "mutate", "export", "share"}),
    "viewer": frozenset({"view", "export"}),
}


class AccessPolicyError(Exception):
    """Raised when an AccessPolicy operation is invalid."""


@dataclass
class AccessPolicy:
    """Sole-user-default access policy for a single resource.

    Multi-user expansion: viewers list and public_link surface the future
    multi-user roles without requiring schema migration.
    """

    resource_type: str
    resource_id: str
    owner_user_id: str
    viewers: list[str] = field(default_factory=list)
    public_link: str | None = None
    public_link_expires_at: float | None = None

    def role_for(self, user_id: str | None) -> ViewerRole:
        if user_id is not None and user_id == self.owner_user_id:
            return "owner"
        if user_id is not None and user_id in self.viewers:
            return "viewer"
        if self.public_link is not None:
            return "viewer"
        return "viewer"

    def allows(self, role: ViewerRole, action: AccessAction) -> bool:
        permitted = _PERMISSION_MATRIX.get(role)
        if permitted is None:
            return False
        return action in permitted

    def activate_public_link(
        self,
        *,
        now: float,
        ttl_seconds: int = _PUBLIC_LINK_TTL_SECONDS,
    ) -> str:
        token = secrets.token_urlsafe(_PUBLIC_LINK_TOKEN_BYTES)
        self.public_link = token
        self.public_link_expires_at = now + ttl_seconds
        return token

    def deactivate_public_link(self) -> None:
        self.public_link = None
        self.public_link_expires_at = None
