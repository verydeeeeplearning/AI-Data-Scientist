"""FastAPI dependency factory for resource boundary enforcement.

Each mutating route declares the `resource_type` + `action` it represents
and a callable that extracts the `resource_id` from the request payload.
The dependency calls :class:`ResourceAccessGuard.enforce` on every call,
raising HTTP 403 with the structured ``forbidden`` payload on deny.

Sole-user mode: actor is unset, the guard's policy lookup misses, and
``sole_user_owner_default`` allows the request. The dependency still
emits an audit entry on every authorise call so introducing real viewers
later does not require route edits.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException, Request

from ds_agent.api.access_middleware import (
    AccessDeniedError,
    AccessRequest,
    forbidden_response,
)
from ds_agent.domain.access import AccessAction


def _resolve_actor_user_id(request: Request) -> str | None:
    """Pick up an actor user id from request state when it has been set.

    Sole-user mode: nothing sets this, so we return ``None`` and the
    guard falls through to the owner-default branch.
    """
    actor = getattr(request.state, "actor_user_id", None)
    if isinstance(actor, str) and actor.strip():
        return actor
    return None


def require_resource_access(
    *,
    resource_type: str,
    action: AccessAction,
    resource_id_extractor: Callable[[Request], Awaitable[str] | str],
) -> Callable[[Request], Awaitable[None]]:
    """Build a FastAPI dependency that enforces access for one route.

    *resource_id_extractor* receives the request and returns the
    resource id (sync or async). Routes that take a typed body should
    extract from the parsed body when they have access; routes that
    only know the id from a query/path parameter can read it directly.
    """

    async def _dependency(request: Request) -> None:
        guard = getattr(request.app.state.app_state, "resource_access_guard", None)
        if guard is None:
            return  # composition incomplete; fail open during tests

        raw = resource_id_extractor(request)
        resource_id = await raw if hasattr(raw, "__await__") else raw  # type: ignore[union-attr]
        if not isinstance(resource_id, str) or not resource_id.strip():
            return  # no resource scope present; nothing to authorise

        try:
            guard.enforce(
                AccessRequest(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=action,
                    actor_user_id=_resolve_actor_user_id(request),
                )
            )
        except AccessDeniedError as denied:
            raise HTTPException(
                status_code=403,
                detail=forbidden_response(denied),
            ) from denied

    return _dependency


def require_session_mutation(resource_type: str, action: AccessAction) -> Any:
    """Convenience: read ``sessionId`` from the parsed JSON body."""

    async def _extract(request: Request) -> str:
        try:
            payload = await request.json()
        except Exception:
            return ""
        if not isinstance(payload, dict):
            return ""
        value = payload.get("sessionId") or payload.get("session_id") or ""
        return value if isinstance(value, str) else ""

    return require_resource_access(
        resource_type=resource_type,
        action=action,
        resource_id_extractor=_extract,
    )
