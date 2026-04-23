"""Application use cases for approval grants.

Wave 2 W2-F phase 2: separates the read/issue/revoke flow from the approval
submit pipeline so the surface (settings UI) can list and revoke grants
without depending on the runtime submit flow, and so future channels (CLI,
Telegram) can request grants the same way.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from ds_agent.domain.entities.approval_grant import (
    DEFAULT_SESSION_TIMEOUT_SECONDS,
    ApprovalGrant,
    ApprovalGrantScope,
)


class ApprovalGrantStoreLike(Protocol):
    def issue(
        self,
        *,
        approval_id: str,
        scope: ApprovalGrantScope,
        risk_code: str,
        kind: str,
        session_id: str,
        workspace_id: str | None,
        actor: str | None,
        source: str | None,
        affected_scopes: list[str] | None,
        ttl_seconds: float | None,
        now: float | None = None,
    ) -> ApprovalGrant: ...

    def list(
        self,
        *,
        session_id: str | None = None,
        workspace_id: str | None = None,
        include_inactive: bool = False,
        now: float | None = None,
    ) -> list[ApprovalGrant]: ...

    def revoke(
        self,
        grant_id: str,
        *,
        actor: str | None = None,
        now: float | None = None,
    ) -> ApprovalGrant | None: ...


@dataclass(slots=True)
class IssueApprovalGrantInput:
    """Input arguments for ``IssueApprovalGrantUseCase``."""

    approval_id: str
    scope: ApprovalGrantScope
    risk_code: str
    kind: str
    session_id: str
    workspace_id: str | None = None
    actor: str | None = None
    source: str | None = None
    affected_scopes: Iterable[str] | None = None
    session_ttl_seconds: float = DEFAULT_SESSION_TIMEOUT_SECONDS


class IssueApprovalGrantUseCase:
    """Persist a session/workspace approval grant from a resolved approval."""

    def __init__(self, store: ApprovalGrantStoreLike) -> None:
        self._store = store

    def execute(self, request: IssueApprovalGrantInput) -> ApprovalGrant:
        if not request.approval_id.strip():
            raise ValueError("approval_id is required")
        if not request.session_id.strip():
            raise ValueError("session_id is required")
        if request.scope not in (ApprovalGrantScope.SESSION, ApprovalGrantScope.WORKSPACE):
            raise ValueError("scope must be 'session' or 'workspace'")

        ttl = (
            request.session_ttl_seconds
            if request.scope == ApprovalGrantScope.SESSION
            else None
        )
        affected = list(request.affected_scopes or [])
        return self._store.issue(
            approval_id=request.approval_id,
            scope=request.scope,
            risk_code=request.risk_code,
            kind=request.kind,
            session_id=request.session_id,
            workspace_id=request.workspace_id,
            actor=request.actor,
            source=request.source,
            affected_scopes=affected,
            ttl_seconds=ttl,
        )


class ListApprovalGrantsUseCase:
    """Return active grants for the operator surface."""

    def __init__(self, store: ApprovalGrantStoreLike) -> None:
        self._store = store

    def execute(
        self,
        *,
        session_id: str | None = None,
        workspace_id: str | None = None,
        include_inactive: bool = False,
    ) -> list[dict[str, Any]]:
        grants = self._store.list(
            session_id=session_id,
            workspace_id=workspace_id,
            include_inactive=include_inactive,
        )
        return [grant.to_dict() for grant in grants]


class RevokeApprovalGrantUseCase:
    """Mark a grant as revoked. Idempotent."""

    def __init__(self, store: ApprovalGrantStoreLike) -> None:
        self._store = store

    def execute(
        self,
        grant_id: str,
        *,
        actor: str | None = None,
    ) -> dict[str, Any]:
        if not grant_id.strip():
            raise ValueError("grant_id is required")
        revoked = self._store.revoke(grant_id, actor=actor)
        if revoked is None:
            raise LookupError(f"Unknown grantId: {grant_id}")
        return revoked.to_dict()
