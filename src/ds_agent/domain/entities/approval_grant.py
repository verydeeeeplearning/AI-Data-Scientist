"""Domain entity for persisted approval grants.

Wave 2 W2-F phase 2 introduces durable session/workspace scope semantics for
approval decisions. Each grant captures who approved what risk pattern under
which scope, when it expires, and whether it has been revoked.

Grants are append-once: revocation flips ``revoked_at`` rather than deleting
the row so audit trails remain intact.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

DEFAULT_SESSION_TIMEOUT_SECONDS: float = 30 * 60.0
"""Session-scope grants expire 30 minutes after they are issued."""


class ApprovalGrantScope(StrEnum):
    """Persistence scope for an approval grant."""

    SESSION = "session"
    WORKSPACE = "workspace"


class ApprovalGrantStatus(StrEnum):
    """Lifecycle states surfaced to the UI."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(slots=True)
class ApprovalGrant:
    """One durable approval grant.

    Attributes:
        grant_id: Stable identifier (12 hex chars) used by revoke endpoints.
        approval_id: Source approval request that produced this grant.
        scope: Session or workspace persistence scope.
        risk_code: Primary policy code (e.g., ``PAT_FILESYSTEM_WRITE``).
        kind: Surface kind (mirrors ``ApprovalRequest.kind``) for UI grouping.
        session_id: Session that approved the grant (always populated).
        workspace_id: Workspace identifier when scope is ``workspace``.
        actor: Operator surface that approved the grant.
        source: ``approval.submit`` source string for audit purposes.
        affected_scopes: Bounded list of impact scopes captured at grant time.
        created_at: Epoch seconds when the grant was issued.
        expires_at: Optional epoch seconds for automatic expiry.
        revoked_at: Set when an operator revokes the grant.
    """

    grant_id: str
    approval_id: str
    scope: ApprovalGrantScope
    risk_code: str
    kind: str
    session_id: str
    workspace_id: str | None = None
    actor: str | None = None
    source: str | None = None
    affected_scopes: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    revoked_at: float | None = None

    def status(self, *, now: float | None = None) -> ApprovalGrantStatus:
        """Return the lifecycle status against an optional clock."""

        if self.revoked_at is not None:
            return ApprovalGrantStatus.REVOKED
        clock = now if now is not None else time.time()
        if self.expires_at is not None and clock >= self.expires_at:
            return ApprovalGrantStatus.EXPIRED
        return ApprovalGrantStatus.ACTIVE

    def is_active(self, *, now: float | None = None) -> bool:
        return self.status(now=now) == ApprovalGrantStatus.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "grantId": self.grant_id,
            "approvalId": self.approval_id,
            "scope": self.scope.value,
            "riskCode": self.risk_code,
            "kind": self.kind,
            "sessionId": self.session_id,
            "workspaceId": self.workspace_id,
            "actor": self.actor,
            "source": self.source,
            "affectedScopes": list(self.affected_scopes),
            "createdAt": self.created_at,
            "expiresAt": self.expires_at,
            "revokedAt": self.revoked_at,
            "status": self.status().value,
        }
