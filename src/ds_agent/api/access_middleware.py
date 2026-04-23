"""Resource access boundary for renderer-facing mutation handlers.

Wraps a callable that receives ``(resource_type, resource_id, actor_user_id, ...)``
and authorises the action via :class:`CheckAccessUseCase` before delegating.
On deny the middleware returns a structured ``forbidden`` payload AND emits an
audit entry through :class:`LogAccessUseCase`.

Sole-user-default behaviour: when no policy has been materialised for the
resource the actor is treated as the implicit owner. The first time an operator
shares a resource a policy is created (see :class:`ShareResourceUseCase`) and
subsequent viewer access is then enforced.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from ds_agent.application.use_cases.check_access_usecase import (
    CheckAccessInput,
    CheckAccessOutput,
    CheckAccessUseCase,
)
from ds_agent.application.use_cases.log_access_usecase import (
    LogAccessInput,
    LogAccessUseCase,
)
from ds_agent.domain.access import AccessAction


class AccessDeniedError(PermissionError):
    """Raised when a mutation is rejected by the access middleware."""

    def __init__(
        self,
        *,
        reason: str,
        resource_type: str,
        resource_id: str,
        action: AccessAction,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.action = action


@dataclass(frozen=True, slots=True)
class AccessRequest:
    """Authorization input for one mutation attempt."""

    resource_type: str
    resource_id: str
    action: AccessAction
    actor_user_id: str | None = None
    public_link_token: str | None = None
    metadata: Mapping[str, object] | None = None
    now: float | None = None


@dataclass(frozen=True, slots=True)
class AccessDecision:
    """Outcome of one middleware authorisation pass."""

    allowed: bool
    reason: str
    role: str | None
    policy_present: bool


class _AccessAuditEmitter(Protocol):
    def execute(self, request: LogAccessInput) -> object: ...


class _AccessAuthorizer(Protocol):
    def execute(self, request: CheckAccessInput) -> CheckAccessOutput: ...


class ResourceAccessGuard:
    """Service that authorises and audits one resource-level action.

    Sole-user-default: a missing policy is treated as the implicit owner case.
    Once a policy exists the existing :class:`CheckAccessUseCase` permission
    matrix is the source of truth.
    """

    def __init__(
        self,
        *,
        check_access: _AccessAuthorizer,
        log_access: _AccessAuditEmitter,
    ) -> None:
        self._check = check_access
        self._log = log_access

    def authorize(self, request: AccessRequest) -> AccessDecision:
        now = time.time() if request.now is None else float(request.now)
        check_input = CheckAccessInput(
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            action=request.action,
            actor_user_id=request.actor_user_id,
            public_link_token=request.public_link_token,
            now=now,
        )
        outcome = self._check.execute(check_input)

        # Sole-user-default: treat missing policy as owner.
        if outcome.reason == "policy_not_found":
            decision = AccessDecision(
                allowed=True,
                reason="sole_user_owner_default",
                role="owner",
                policy_present=False,
            )
        else:
            decision = AccessDecision(
                allowed=outcome.allowed,
                reason=outcome.reason,
                role=outcome.role,
                policy_present=True,
            )

        self._log.execute(
            LogAccessInput(
                resource_type=request.resource_type,
                resource_id=request.resource_id,
                action=request.action,
                allowed=decision.allowed,
                actor_user_id=request.actor_user_id,
                role=outcome.role,
                reason=decision.reason,
                metadata=request.metadata,
                occurred_at=now,
            )
        )

        return decision

    def enforce(self, request: AccessRequest) -> AccessDecision:
        decision = self.authorize(request)
        if not decision.allowed:
            raise AccessDeniedError(
                reason=decision.reason,
                resource_type=request.resource_type,
                resource_id=request.resource_id,
                action=request.action,
            )
        return decision


def build_resource_access_guard(
    *,
    policy_store: object,
    log_store: object,
) -> ResourceAccessGuard:
    """Composition root for the renderer-facing access guard."""

    return ResourceAccessGuard(
        check_access=CheckAccessUseCase(policy_store),  # type: ignore[arg-type]
        log_access=LogAccessUseCase(log_store),  # type: ignore[arg-type]
    )


def forbidden_response(error: AccessDeniedError) -> dict[str, object]:
    """Structured ``forbidden`` payload returned to the renderer."""

    return {
        "ok": False,
        "error": {
            "code": "FORBIDDEN",
            "reason": error.reason,
            "resourceType": error.resource_type,
            "resourceId": error.resource_id,
            "action": error.action,
        },
    }
