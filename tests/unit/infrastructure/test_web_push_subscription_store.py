"""Tests for JsonWebPushSubscriptionStore (Wave 4 PLAN_06b)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ds_agent.infrastructure.persistence.web_push_subscription_store import (
    JsonWebPushSubscriptionStore,
    WebPushSubscription,
)


def _sub(endpoint: str = "https://push.example/abc") -> WebPushSubscription:
    return WebPushSubscription(
        endpoint=endpoint,
        p256dh_key="p256-fake",
        auth_key="auth-fake",
        created_at=datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC),
    )


def test_register_then_list_returns_subscription(tmp_path: Path) -> None:
    store = JsonWebPushSubscriptionStore(base_dir=tmp_path)

    store.register("op-1", _sub("e1"))
    items = store.list_for("op-1")

    assert len(items) == 1
    assert items[0].endpoint == "e1"
    assert items[0].p256dh_key == "p256-fake"


def test_register_dedupes_by_endpoint_and_refreshes_last_used(
    tmp_path: Path,
) -> None:
    store = JsonWebPushSubscriptionStore(base_dir=tmp_path)
    store.register("op-1", _sub("e1"))

    refreshed = WebPushSubscription(
        endpoint="e1",
        p256dh_key="p256-rotated",
        auth_key="auth-rotated",
        created_at=datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC),
    )
    store.register("op-1", refreshed)

    items = store.list_for("op-1")
    assert len(items) == 1, "must not duplicate same endpoint"
    assert items[0].p256dh_key == "p256-rotated"
    assert items[0].last_used_at is not None


def test_unregister_removes_only_target_endpoint(tmp_path: Path) -> None:
    store = JsonWebPushSubscriptionStore(base_dir=tmp_path)
    store.register("op-1", _sub("e1"))
    store.register("op-1", _sub("e2"))

    removed = store.unregister("op-1", "e1")
    assert removed is True
    items = store.list_for("op-1")
    assert {item.endpoint for item in items} == {"e2"}

    # Idempotent: unregistering an unknown endpoint just returns False.
    assert store.unregister("op-1", "unknown") is False


def test_subscriptions_survive_store_recreation(tmp_path: Path) -> None:
    """A new store instance over the same dir must see existing data."""
    first = JsonWebPushSubscriptionStore(base_dir=tmp_path)
    first.register("op-1", _sub("e1"))
    first.register("op-1", _sub("e2"))

    second = JsonWebPushSubscriptionStore(base_dir=tmp_path)
    items = second.list_for("op-1")
    assert {item.endpoint for item in items} == {"e1", "e2"}


def test_list_for_unknown_operator_returns_empty(tmp_path: Path) -> None:
    store = JsonWebPushSubscriptionStore(base_dir=tmp_path)
    assert store.list_for("never-existed") == []


def test_subscription_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        WebPushSubscription(
            endpoint="e",
            p256dh_key="p",
            auth_key="a",
            created_at=datetime(2026, 4, 20, 12, 0, 0),  # naive
        )


def test_subscription_rejects_empty_keys() -> None:
    with pytest.raises(ValueError):
        WebPushSubscription(
            endpoint="e",
            p256dh_key="",
            auth_key="a",
            created_at=datetime(2026, 4, 20, tzinfo=UTC),
        )
