from __future__ import annotations

import pytest

from ds_agent.application.use_cases.share_resource_usecase import (
    ShareResourceInput,
    ShareResourceUseCase,
)
from ds_agent.domain.access import AccessPolicy, AccessPolicyError


class _FakeAccessPolicyStore:
    def __init__(self) -> None:
        self._policies: dict[tuple[str, str], AccessPolicy] = {}

    def load(self, *, resource_type: str, resource_id: str) -> AccessPolicy | None:
        return self._policies.get((resource_type, resource_id))

    def save(self, policy: AccessPolicy) -> AccessPolicy:
        self._policies[(policy.resource_type, policy.resource_id)] = policy
        return policy


def test_share_resource_creates_policy_and_deduplicates_viewers() -> None:
    store = _FakeAccessPolicyStore()
    use_case = ShareResourceUseCase(store)

    result = use_case.execute(
        ShareResourceInput(
            resource_type="run",
            resource_id="run-1",
            owner_user_id="alice",
            viewer_user_ids=["bob", "bob", "alice", "charlie", " "],
        )
    )

    assert result.created is True
    assert result.policy.owner_user_id == "alice"
    assert result.policy.viewers == ["bob", "charlie"]
    assert result.public_link_enabled is False


def test_share_resource_replaces_viewers_and_enables_public_link() -> None:
    store = _FakeAccessPolicyStore()
    existing = AccessPolicy(
        resource_type="run",
        resource_id="run-1",
        owner_user_id="alice",
        viewers=["bob"],
    )
    store.save(existing)
    use_case = ShareResourceUseCase(store)

    result = use_case.execute(
        ShareResourceInput(
            resource_type="run",
            resource_id="run-1",
            owner_user_id="alice",
            viewer_user_ids=["charlie"],
            enable_public_link=True,
            public_link_ttl_seconds=60,
            now=100.0,
        )
    )

    assert result.created is False
    assert result.policy.viewers == ["charlie"]
    assert result.policy.public_link is not None
    assert result.policy.public_link_expires_at == 160.0
    assert result.public_link_enabled is True


def test_share_resource_preserves_viewers_when_not_provided() -> None:
    store = _FakeAccessPolicyStore()
    existing = AccessPolicy(
        resource_type="run",
        resource_id="run-1",
        owner_user_id="alice",
        viewers=["bob"],
    )
    store.save(existing)
    use_case = ShareResourceUseCase(store)

    result = use_case.execute(
        ShareResourceInput(
            resource_type="run",
            resource_id="run-1",
            owner_user_id="alice",
            enable_public_link=True,
            public_link_ttl_seconds=60,
            now=10.0,
        )
    )

    assert result.policy.viewers == ["bob"]


def test_share_resource_blocks_non_owner_actor() -> None:
    store = _FakeAccessPolicyStore()
    store.save(
        AccessPolicy(
            resource_type="run",
            resource_id="run-1",
            owner_user_id="alice",
            viewers=["bob"],
        )
    )
    use_case = ShareResourceUseCase(store)

    with pytest.raises(PermissionError):
        use_case.execute(
            ShareResourceInput(
                resource_type="run",
                resource_id="run-1",
                owner_user_id="alice",
                actor_user_id="bob",
                viewer_user_ids=["charlie"],
            )
        )


def test_share_resource_rejects_conflicting_link_flags() -> None:
    store = _FakeAccessPolicyStore()
    use_case = ShareResourceUseCase(store)

    with pytest.raises(AccessPolicyError):
        use_case.execute(
            ShareResourceInput(
                resource_type="run",
                resource_id="run-1",
                owner_user_id="alice",
                enable_public_link=True,
                disable_public_link=True,
            )
        )
