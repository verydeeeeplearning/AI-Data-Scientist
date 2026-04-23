"""Application use case for resource sharing policy updates."""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from ds_agent.domain.access import AccessPolicy, AccessPolicyError


class AccessPolicyStorePort(Protocol):
    """Storage port for resource access policies."""

    def load(
        self,
        *,
        resource_type: str,
        resource_id: str,
    ) -> AccessPolicy | None: ...

    def save(self, policy: AccessPolicy) -> AccessPolicy: ...


@dataclass(frozen=True, slots=True)
class ShareResourceInput:
    """Requested policy mutation for one resource."""

    resource_type: str
    resource_id: str
    owner_user_id: str
    actor_user_id: str | None = None
    viewer_user_ids: Iterable[str] | None = None
    enable_public_link: bool = False
    disable_public_link: bool = False
    public_link_ttl_seconds: int = 7 * 24 * 60 * 60
    now: float | None = None


@dataclass(frozen=True, slots=True)
class ShareResourceOutput:
    """Updated sharing state returned to the adapter."""

    policy: AccessPolicy
    created: bool
    public_link_enabled: bool


class ShareResourceUseCase:
    """Create or update the share policy for one resource.

    The use case intentionally stays conservative:
    - only an ``owner`` may execute the share mutation
    - public links are opt-in and bounded by TTL
    - viewer lists are replaced only when explicitly provided
    """

    def __init__(self, store: AccessPolicyStorePort) -> None:
        self._store = store

    def execute(self, request: ShareResourceInput) -> ShareResourceOutput:
        resource_type = request.resource_type.strip()
        resource_id = request.resource_id.strip()
        owner_user_id = request.owner_user_id.strip()
        actor_user_id = (
            request.actor_user_id.strip()
            if isinstance(request.actor_user_id, str) and request.actor_user_id.strip()
            else owner_user_id
        )

        if not resource_type:
            raise ValueError("resource_type is required")
        if not resource_id:
            raise ValueError("resource_id is required")
        if not owner_user_id:
            raise ValueError("owner_user_id is required")
        if request.enable_public_link and request.disable_public_link:
            raise AccessPolicyError("public link cannot be enabled and disabled together")
        if request.enable_public_link and request.public_link_ttl_seconds <= 0:
            raise ValueError("public_link_ttl_seconds must be positive")

        existing = self._store.load(resource_type=resource_type, resource_id=resource_id)
        created = existing is None
        policy = (
            AccessPolicy(
                resource_type=resource_type,
                resource_id=resource_id,
                owner_user_id=owner_user_id,
            )
            if existing is None
            else existing
        )

        if policy.owner_user_id != owner_user_id:
            raise AccessPolicyError("owner_user_id does not match the existing policy owner")

        actor_role = policy.role_for(actor_user_id)
        if not policy.allows(actor_role, "share"):
            raise PermissionError("only the resource owner may share this resource")

        if request.viewer_user_ids is not None:
            policy.viewers = self._normalize_viewers(
                request.viewer_user_ids,
                owner_user_id=policy.owner_user_id,
            )

        now = time.time() if request.now is None else float(request.now)
        if request.enable_public_link:
            policy.activate_public_link(
                now=now,
                ttl_seconds=int(request.public_link_ttl_seconds),
            )
        elif request.disable_public_link:
            policy.deactivate_public_link()

        saved = self._store.save(policy)
        return ShareResourceOutput(
            policy=saved,
            created=created,
            public_link_enabled=saved.public_link is not None,
        )

    @staticmethod
    def _normalize_viewers(
        viewer_user_ids: Iterable[str],
        *,
        owner_user_id: str,
    ) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for viewer_user_id in viewer_user_ids:
            value = str(viewer_user_id).strip()
            if not value or value == owner_user_id or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized
