"""Tests for DispatchWebPushUseCase (Wave 4 PLAN_06b)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ds_agent.application.use_cases.dispatch_web_push_usecase import (
    SKIP_NO_SUBSCRIPTIONS,
    SKIP_NOT_ELIGIBLE,
    SKIP_TRANSPORT_UNAVAILABLE,
    DispatchWebPushUseCase,
    WebPushSubscriptionStorePort,
    WebPushTransportPort,
    WebPushTransportUnavailableError,
)
from ds_agent.domain.notification import Notification, NotificationCategory


@dataclass(frozen=True, slots=True)
class _FakeSubscription:
    endpoint: str = "https://push.example/abc"
    p256dh_key: str = "p256-fake"
    auth_key: str = "auth-fake"


class _RecordingTransport(WebPushTransportPort):
    def __init__(self) -> None:
        self.calls: list[tuple[_FakeSubscription, Notification]] = []

    def deliver(self, *, operator_id, subscription, notification):  # type: ignore[override]
        self.calls.append((subscription, notification))
        return f"tid-{len(self.calls)}"


class _UnavailableTransport(WebPushTransportPort):
    def deliver(self, *, operator_id, subscription, notification):  # type: ignore[override]
        raise WebPushTransportUnavailableError("vapid_keys_missing")


class _FixedStore(WebPushSubscriptionStorePort):
    def __init__(self, subscriptions: list[_FakeSubscription]) -> None:
        self._subs = subscriptions

    def list_for(self, operator_id: str):  # type: ignore[override]
        return list(self._subs)


def _approval() -> Notification:
    return Notification(
        category=NotificationCategory.APPROVAL,
        title="approve deploy",
        body="risk: medium",
    )


def _info() -> Notification:
    return Notification(
        category=NotificationCategory.INFO,
        title="stage 3 done",
        body="b",
    )


def _error() -> Notification:
    return Notification(
        category=NotificationCategory.ERROR,
        title="boom",
        body="b",
    )


def test_eligible_category_dispatches_to_every_subscription() -> None:
    transport = _RecordingTransport()
    store = _FixedStore([_FakeSubscription("e1"), _FakeSubscription("e2")])
    uc = DispatchWebPushUseCase(transport=transport, subscription_store=store)

    result = uc.execute(operator_id="op1", notification=_approval())

    assert result.delivered_count == 2
    assert result.skipped_reason is None
    assert [call[0].endpoint for call in transport.calls] == ["e1", "e2"]


def test_error_category_is_eligible_too() -> None:
    transport = _RecordingTransport()
    store = _FixedStore([_FakeSubscription()])
    uc = DispatchWebPushUseCase(transport=transport, subscription_store=store)

    result = uc.execute(operator_id="op1", notification=_error())

    assert result.delivered_count == 1
    assert result.skipped_reason is None


def test_ineligible_category_is_skipped_without_touching_store() -> None:
    transport = _RecordingTransport()

    class _RecordingStore(WebPushSubscriptionStorePort):
        def __init__(self) -> None:
            self.calls: list[str] = []

        def list_for(self, operator_id: str):  # type: ignore[override]
            self.calls.append(operator_id)
            return []

    store = _RecordingStore()
    uc = DispatchWebPushUseCase(transport=transport, subscription_store=store)

    result = uc.execute(operator_id="op1", notification=_info())

    assert result.delivered_count == 0
    assert result.skipped_reason == SKIP_NOT_ELIGIBLE
    assert transport.calls == []
    assert store.calls == [], "store must not be queried for ineligible categories"


def test_no_subscriptions_skips_with_dedicated_reason() -> None:
    transport = _RecordingTransport()
    store = _FixedStore([])
    uc = DispatchWebPushUseCase(transport=transport, subscription_store=store)

    result = uc.execute(operator_id="op1", notification=_approval())

    assert result.delivered_count == 0
    assert result.skipped_reason == SKIP_NO_SUBSCRIPTIONS
    assert transport.calls == []


def test_transport_unavailable_returns_skip_without_crashing() -> None:
    transport = _UnavailableTransport()
    store = _FixedStore([_FakeSubscription()])
    uc = DispatchWebPushUseCase(transport=transport, subscription_store=store)

    result = uc.execute(operator_id="op1", notification=_approval())

    assert result.delivered_count == 0
    assert result.skipped_reason == SKIP_TRANSPORT_UNAVAILABLE


def test_partial_delivery_then_transport_unavailable_keeps_count() -> None:
    """If transport works once then fails, we report what we delivered."""
    calls: list[str] = []

    class _Flaky(WebPushTransportPort):
        def deliver(self, *, operator_id, subscription, notification):  # type: ignore[override]
            calls.append(subscription.endpoint)
            if len(calls) == 1:
                return "tid-1"
            raise WebPushTransportUnavailableError("dropped")

    store = _FixedStore([_FakeSubscription("e1"), _FakeSubscription("e2")])
    uc = DispatchWebPushUseCase(transport=_Flaky(), subscription_store=store)
    now = datetime.now(UTC)
    assert now is not None  # tz-aware sanity for record

    result = uc.execute(operator_id="op1", notification=_approval())
    assert result.delivered_count == 1
    assert result.skipped_reason == SKIP_TRANSPORT_UNAVAILABLE
