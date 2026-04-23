"""Resource boundary middleware contract."""

from __future__ import annotations

import pytest

from ds_agent.api.access_middleware import (
    AccessDeniedError,
    AccessRequest,
    ResourceAccessGuard,
    build_resource_access_guard,
    forbidden_response,
)
from ds_agent.application.use_cases.log_access_usecase import LogAccessUseCase
from ds_agent.domain.access import AccessPolicy


class _FakeAccessPolicyStore:
    def __init__(self) -> None:
        self._policies: dict[tuple[str, str], AccessPolicy] = {}

    def load(self, *, resource_type: str, resource_id: str) -> AccessPolicy | None:
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


def _build_guard() -> tuple[ResourceAccessGuard, _FakeAccessPolicyStore, _RecordingAccessLogStore]:
    policies = _FakeAccessPolicyStore()
    log_store = _RecordingAccessLogStore()
    guard = build_resource_access_guard(policy_store=policies, log_store=log_store)
    return guard, policies, log_store


def test_sole_user_owner_default_when_no_policy_exists() -> None:
    guard, _policies, log_store = _build_guard()

    decision = guard.authorize(
        AccessRequest(
            resource_type="run",
            resource_id="run-1",
            action="mutate",
            actor_user_id="alice",
        )
    )

    assert decision.allowed is True
    assert decision.reason == "sole_user_owner_default"
    assert decision.role == "owner"
    assert decision.policy_present is False
    # audit entry written even on allow
    assert len(log_store.entries) == 1
    entry = log_store.entries[0]
    assert entry.allowed is True  # type: ignore[attr-defined]
    assert entry.action == "mutate"  # type: ignore[attr-defined]


def test_owner_mutation_passes_when_policy_exists() -> None:
    guard, policies, log_store = _build_guard()
    policies.save(
        AccessPolicy(
            resource_type="run",
            resource_id="run-1",
            owner_user_id="alice",
            viewers=["bob"],
        )
    )

    decision = guard.authorize(
        AccessRequest(
            resource_type="run",
            resource_id="run-1",
            action="mutate",
            actor_user_id="alice",
        )
    )

    assert decision.allowed is True
    assert decision.role == "owner"
    assert decision.policy_present is True
    assert log_store.entries[-1].allowed is True  # type: ignore[attr-defined]


def test_viewer_mutation_denied_and_logged() -> None:
    guard, policies, log_store = _build_guard()
    policies.save(
        AccessPolicy(
            resource_type="run",
            resource_id="run-1",
            owner_user_id="alice",
            viewers=["bob"],
        )
    )

    decision = guard.authorize(
        AccessRequest(
            resource_type="run",
            resource_id="run-1",
            action="mutate",
            actor_user_id="bob",
        )
    )

    assert decision.allowed is False
    assert decision.reason == "action_forbidden"
    assert decision.role == "viewer"
    assert log_store.entries[-1].allowed is False  # type: ignore[attr-defined]
    # actor must not be persisted in the clear
    assert log_store.entries[-1].actor_ref != "bob"  # type: ignore[attr-defined]
    assert log_store.entries[-1].actor_ref.startswith("user:")  # type: ignore[attr-defined]


def test_enforce_raises_access_denied_for_viewer() -> None:
    guard, policies, _log = _build_guard()
    policies.save(
        AccessPolicy(
            resource_type="artifact",
            resource_id="art-7",
            owner_user_id="alice",
            viewers=["bob"],
        )
    )

    with pytest.raises(AccessDeniedError) as excinfo:
        guard.enforce(
            AccessRequest(
                resource_type="artifact",
                resource_id="art-7",
                action="mutate",
                actor_user_id="bob",
            )
        )

    error = excinfo.value
    assert error.reason == "action_forbidden"
    assert error.action == "mutate"
    payload = forbidden_response(error)
    assert payload["ok"] is False
    inner = payload["error"]
    assert isinstance(inner, dict)
    assert inner["code"] == "FORBIDDEN"
    assert inner["resourceType"] == "artifact"
    assert inner["resourceId"] == "art-7"


def test_log_access_use_case_is_invoked_via_composition() -> None:
    # Spot-check that build_resource_access_guard composes a real LogAccessUseCase
    # so the audit emitter applies actor hashing + metadata sanitisation.
    policies = _FakeAccessPolicyStore()
    log_store = _RecordingAccessLogStore()
    guard = build_resource_access_guard(policy_store=policies, log_store=log_store)

    # Internal sanity — the emitter is the production LogAccessUseCase.
    assert isinstance(guard._log, LogAccessUseCase)

    guard.authorize(
        AccessRequest(
            resource_type="run",
            resource_id="run-9",
            action="mutate",
            actor_user_id="alice@example.com",
            metadata={"surface": "electron", "user_email": "alice@example.com"},
        )
    )

    entry = log_store.entries[-1]
    # email-bearing metadata key is stripped
    assert "user_email" not in entry.metadata  # type: ignore[attr-defined]
    assert entry.metadata.get("surface") == "electron"  # type: ignore[attr-defined]
