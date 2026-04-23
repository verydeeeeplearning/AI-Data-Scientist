from __future__ import annotations

import pytest

from ds_agent.domain.access import AccessPolicy


def _policy(owner: str = "local", viewers: list[str] | None = None) -> AccessPolicy:
    return AccessPolicy(
        resource_type="run",
        resource_id="run-1",
        owner_user_id=owner,
        viewers=viewers or [],
    )


class TestRoleResolution:
    def test_owner_user_resolves_owner(self) -> None:
        assert _policy(owner="alice").role_for("alice") == "owner"

    def test_listed_viewer_resolves_viewer(self) -> None:
        assert _policy(owner="alice", viewers=["bob"]).role_for("bob") == "viewer"

    def test_unknown_user_resolves_viewer(self) -> None:
        assert _policy(owner="alice").role_for("charlie") == "viewer"

    def test_anonymous_no_link_resolves_viewer(self) -> None:
        # Sole-user environment passes None; no public link yet.
        assert _policy(owner="alice").role_for(None) == "viewer"

    def test_public_link_active_grants_viewer_to_anonymous(self) -> None:
        policy = _policy()
        policy.activate_public_link(now=0.0)
        assert policy.role_for(None) == "viewer"


class TestPermissionMatrix:
    @pytest.mark.parametrize("action", ["view", "mutate", "export", "share"])
    def test_owner_allows_every_action(self, action: str) -> None:
        assert _policy().allows("owner", action) is True  # type: ignore[arg-type]

    @pytest.mark.parametrize("action", ["view", "export"])
    def test_viewer_can_view_and_export(self, action: str) -> None:
        assert _policy().allows("viewer", action) is True  # type: ignore[arg-type]

    @pytest.mark.parametrize("action", ["mutate", "share"])
    def test_viewer_cannot_mutate_or_share(self, action: str) -> None:
        assert _policy().allows("viewer", action) is False  # type: ignore[arg-type]


class TestPublicLink:
    def test_default_link_is_none(self) -> None:
        assert _policy().public_link is None

    def test_activate_sets_token_and_expiry(self) -> None:
        policy = _policy()
        token = policy.activate_public_link(now=100.0, ttl_seconds=3600)
        assert token == policy.public_link
        assert policy.public_link_expires_at == 100.0 + 3600

    def test_deactivate_clears_token(self) -> None:
        policy = _policy()
        policy.activate_public_link(now=0.0)
        policy.deactivate_public_link()
        assert policy.public_link is None
        assert policy.public_link_expires_at is None

    def test_token_is_url_safe_and_long(self) -> None:
        policy = _policy()
        token = policy.activate_public_link(now=0.0)
        assert len(token) >= 32
        assert "/" not in token
        assert "+" not in token
