"""FastAPI access dependency factory contract.

Verifies that ``require_resource_access`` and ``require_session_mutation``
call the underlying ``ResourceAccessGuard`` and translate denial into
HTTP 403 with the structured forbidden payload.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from ds_agent.api.access_middleware import (
    AccessDeniedError,
    AccessRequest,
    ResourceAccessGuard,
    build_resource_access_guard,
)
from ds_agent.api.dependencies.access import (
    require_resource_access,
    require_session_mutation,
)
from ds_agent.domain.access import AccessPolicy


class _FakeAccessPolicyStore:
    def __init__(self) -> None:
        self._policies: dict[tuple[str, str], AccessPolicy] = {}

    def load(
        self, *, resource_type: str, resource_id: str
    ) -> AccessPolicy | None:
        return self._policies.get((resource_type, resource_id))

    def save(self, policy: AccessPolicy) -> AccessPolicy:
        self._policies[(policy.resource_type, policy.resource_id)] = policy
        return policy


class _RecordingAccessLogStore:
    def __init__(self) -> None:
        self.entries: list[object] = []

    def append(self, entry):  # type: ignore[no-untyped-def]
        self.entries.append(entry)
        return entry


def _build_guard() -> tuple[ResourceAccessGuard, _FakeAccessPolicyStore]:
    policies = _FakeAccessPolicyStore()
    log_store = _RecordingAccessLogStore()
    guard = build_resource_access_guard(policy_store=policies, log_store=log_store)
    return guard, policies


def _build_request(
    *, guard: ResourceAccessGuard | None, body: dict | None = None,
    actor: str | None = None,
) -> MagicMock:
    request = MagicMock()
    request.app.state.app_state.resource_access_guard = guard
    request.state.actor_user_id = actor
    if body is not None:
        async def _json() -> dict:
            return body
        request.json = _json
    return request


@pytest.mark.asyncio
async def test_dependency_allows_when_no_policy_exists() -> None:
    guard, _policies = _build_guard()
    dep = require_resource_access(
        resource_type="run",
        action="mutate",
        resource_id_extractor=lambda _req: "run-1",
    )
    request = _build_request(guard=guard)
    result = await dep(request)
    assert result is None


@pytest.mark.asyncio
async def test_dependency_raises_403_for_viewer_mutation() -> None:
    guard, policies = _build_guard()
    policies.save(
        AccessPolicy(
            resource_type="run",
            resource_id="run-1",
            owner_user_id="alice",
            viewers=["bob"],
        )
    )
    dep = require_resource_access(
        resource_type="run",
        action="mutate",
        resource_id_extractor=lambda _req: "run-1",
    )
    request = _build_request(guard=guard, actor="bob")

    with pytest.raises(HTTPException) as excinfo:
        await dep(request)

    assert excinfo.value.status_code == 403
    detail = excinfo.value.detail
    assert isinstance(detail, dict)
    assert detail["ok"] is False
    inner = detail["error"]
    assert isinstance(inner, dict)
    assert inner["code"] == "FORBIDDEN"
    assert inner["resourceType"] == "run"
    assert inner["resourceId"] == "run-1"
    assert inner["action"] == "mutate"


@pytest.mark.asyncio
async def test_dependency_owner_passes_when_policy_exists() -> None:
    guard, policies = _build_guard()
    policies.save(
        AccessPolicy(
            resource_type="run",
            resource_id="run-2",
            owner_user_id="alice",
            viewers=["bob"],
        )
    )
    dep = require_resource_access(
        resource_type="run",
        action="mutate",
        resource_id_extractor=lambda _req: "run-2",
    )
    request = _build_request(guard=guard, actor="alice")
    result = await dep(request)
    assert result is None


@pytest.mark.asyncio
async def test_dependency_skips_when_resource_id_is_empty() -> None:
    guard, _policies = _build_guard()
    dep = require_resource_access(
        resource_type="run",
        action="mutate",
        resource_id_extractor=lambda _req: "",
    )
    request = _build_request(guard=guard)
    result = await dep(request)
    assert result is None


@pytest.mark.asyncio
async def test_dependency_fails_open_when_guard_missing() -> None:
    """During tests / partial composition the dependency must not 500."""
    dep = require_resource_access(
        resource_type="run",
        action="mutate",
        resource_id_extractor=lambda _req: "run-3",
    )
    request = _build_request(guard=None)
    result = await dep(request)
    assert result is None


@pytest.mark.asyncio
async def test_session_mutation_extracts_session_id_from_body() -> None:
    guard, _policies = _build_guard()
    dep = require_session_mutation("session", "mutate")
    request = _build_request(guard=guard, body={"sessionId": "sess-99"})
    result = await dep(request)
    assert result is None  # sole-user-default allows


@pytest.mark.asyncio
async def test_session_mutation_handles_snake_case_alias() -> None:
    guard, _policies = _build_guard()
    dep = require_session_mutation("session", "mutate")
    request = _build_request(guard=guard, body={"session_id": "sess-77"})
    result = await dep(request)
    assert result is None


@pytest.mark.asyncio
async def test_session_mutation_skips_when_body_missing() -> None:
    guard, _policies = _build_guard()
    dep = require_session_mutation("session", "mutate")
    request = MagicMock()
    request.app.state.app_state.resource_access_guard = guard
    request.state.actor_user_id = None

    async def _broken_json() -> dict:
        raise ValueError("no body")
    request.json = _broken_json

    result = await dep(request)
    assert result is None


def test_access_request_dataclass_shape() -> None:
    """Document the AccessRequest constructor contract."""
    req = AccessRequest(
        resource_type="run",
        resource_id="run-1",
        action="mutate",
        actor_user_id="alice",
    )
    assert req.resource_type == "run"
    assert req.action == "mutate"
    # AccessDeniedError carries the same fields for forbidden_response()
    err = AccessDeniedError(
        reason="action_forbidden",
        resource_type="run",
        resource_id="run-1",
        action="mutate",
    )
    assert err.reason == "action_forbidden"
