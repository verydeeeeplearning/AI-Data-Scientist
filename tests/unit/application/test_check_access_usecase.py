from __future__ import annotations

from ds_agent.application.use_cases.check_access_usecase import (
    CheckAccessInput,
    CheckAccessUseCase,
)
from ds_agent.domain.access import AccessPolicy


class _FakeAccessPolicyStore:
    def __init__(self) -> None:
        self._policies: dict[tuple[str, str], AccessPolicy] = {}
        self.saved_policies: list[AccessPolicy] = []

    def load(self, *, resource_type: str, resource_id: str) -> AccessPolicy | None:
        return self._policies.get((resource_type, resource_id))

    def save(self, policy: AccessPolicy) -> AccessPolicy:
        self._policies[(policy.resource_type, policy.resource_id)] = policy
        self.saved_policies.append(policy)
        return policy


def test_check_access_returns_not_found_when_policy_missing() -> None:
    use_case = CheckAccessUseCase(_FakeAccessPolicyStore())

    result = use_case.execute(
        CheckAccessInput(
            resource_type="run",
            resource_id="run-1",
            action="view",
            actor_user_id="alice",
        )
    )

    assert result.allowed is False
    assert result.reason == "policy_not_found"
    assert result.policy is None


def test_owner_can_mutate_resource() -> None:
    store = _FakeAccessPolicyStore()
    store.save(
        AccessPolicy(
            resource_type="run",
            resource_id="run-1",
            owner_user_id="alice",
            viewers=["bob"],
        )
    )
    use_case = CheckAccessUseCase(store)

    result = use_case.execute(
        CheckAccessInput(
            resource_type="run",
            resource_id="run-1",
            action="mutate",
            actor_user_id="alice",
        )
    )

    assert result.allowed is True
    assert result.role == "owner"
    assert result.reason == "allowed"


def test_viewer_cannot_share_resource() -> None:
    store = _FakeAccessPolicyStore()
    store.save(
        AccessPolicy(
            resource_type="run",
            resource_id="run-1",
            owner_user_id="alice",
            viewers=["bob"],
        )
    )
    use_case = CheckAccessUseCase(store)

    result = use_case.execute(
        CheckAccessInput(
            resource_type="run",
            resource_id="run-1",
            action="share",
            actor_user_id="bob",
        )
    )

    assert result.allowed is False
    assert result.role == "viewer"
    assert result.reason == "action_forbidden"


def test_anonymous_requires_public_link() -> None:
    store = _FakeAccessPolicyStore()
    store.save(
        AccessPolicy(
            resource_type="run",
            resource_id="run-1",
            owner_user_id="alice",
        )
    )
    use_case = CheckAccessUseCase(store)

    result = use_case.execute(
        CheckAccessInput(
            resource_type="run",
            resource_id="run-1",
            action="view",
        )
    )

    assert result.allowed is False
    assert result.reason == "anonymous_requires_public_link"


def test_valid_public_link_allows_anonymous_export() -> None:
    store = _FakeAccessPolicyStore()
    policy = AccessPolicy(
        resource_type="run",
        resource_id="run-1",
        owner_user_id="alice",
    )
    policy.activate_public_link(now=100.0, ttl_seconds=60)
    store.save(policy)
    use_case = CheckAccessUseCase(store)

    result = use_case.execute(
        CheckAccessInput(
            resource_type="run",
            resource_id="run-1",
            action="export",
            public_link_token=policy.public_link,
            now=120.0,
        )
    )

    assert result.allowed is True
    assert result.role == "viewer"
    assert result.reason == "allowed"


def test_expired_public_link_is_denied_and_deactivated() -> None:
    store = _FakeAccessPolicyStore()
    policy = AccessPolicy(
        resource_type="run",
        resource_id="run-1",
        owner_user_id="alice",
    )
    policy.activate_public_link(now=0.0, ttl_seconds=10)
    store.save(policy)
    use_case = CheckAccessUseCase(store)

    result = use_case.execute(
        CheckAccessInput(
            resource_type="run",
            resource_id="run-1",
            action="view",
            public_link_token=policy.public_link,
            now=15.0,
        )
    )

    assert result.allowed is False
    assert result.reason == "public_link_expired"
    assert store.saved_policies[-1].public_link is None
