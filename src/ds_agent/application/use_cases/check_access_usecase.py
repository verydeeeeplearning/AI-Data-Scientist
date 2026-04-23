"""Application use case for access checks against one resource policy."""

from __future__ import annotations

import time
from dataclasses import dataclass

from ds_agent.domain.access import AccessAction, AccessPolicy
from ds_agent.domain.access.viewer_role import ViewerRole

from .share_resource_usecase import AccessPolicyStorePort


@dataclass(frozen=True, slots=True)
class CheckAccessInput:
    """Requested action to authorize."""

    resource_type: str
    resource_id: str
    action: AccessAction
    actor_user_id: str | None = None
    public_link_token: str | None = None
    now: float | None = None


@dataclass(frozen=True, slots=True)
class CheckAccessOutput:
    """Authorization decision for one access attempt."""

    allowed: bool
    reason: str
    policy: AccessPolicy | None = None
    role: ViewerRole | None = None


class CheckAccessUseCase:
    """Resolve a role and apply the existing access permission matrix."""

    def __init__(self, store: AccessPolicyStorePort) -> None:
        self._store = store

    def execute(self, request: CheckAccessInput) -> CheckAccessOutput:
        resource_type = request.resource_type.strip()
        resource_id = request.resource_id.strip()
        if not resource_type:
            raise ValueError("resource_type is required")
        if not resource_id:
            raise ValueError("resource_id is required")

        policy = self._store.load(resource_type=resource_type, resource_id=resource_id)
        if policy is None:
            return CheckAccessOutput(
                allowed=False,
                reason="policy_not_found",
            )

        now = time.time() if request.now is None else float(request.now)
        role, denied_reason = self._resolve_role(policy, request, now=now)
        if denied_reason is not None:
            return CheckAccessOutput(
                allowed=False,
                reason=denied_reason,
                policy=policy,
            )

        allowed = policy.allows(role, request.action)
        return CheckAccessOutput(
            allowed=allowed,
            reason="allowed" if allowed else "action_forbidden",
            policy=policy,
            role=role,
        )

    def _resolve_role(
        self,
        policy: AccessPolicy,
        request: CheckAccessInput,
        *,
        now: float,
    ) -> tuple[ViewerRole, str | None]:
        actor_user_id = (
            request.actor_user_id.strip()
            if isinstance(request.actor_user_id, str) and request.actor_user_id.strip()
            else None
        )
        if actor_user_id is not None:
            return policy.role_for(actor_user_id), None

        token = (
            request.public_link_token.strip()
            if isinstance(request.public_link_token, str) and request.public_link_token.strip()
            else None
        )
        if token is None:
            return "viewer", "anonymous_requires_public_link"
        if policy.public_link is None or token != policy.public_link:
            return "viewer", "invalid_public_link"
        if policy.public_link_expires_at is not None and policy.public_link_expires_at <= now:
            policy.deactivate_public_link()
            self._store.save(policy)
            return "viewer", "public_link_expired"
        return "viewer", None
