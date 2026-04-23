"""Use case: dispatch a notification through the web push lane.

Wave 4 PLAN_06b. Web push is the *mobile-only* lane that fans out
notifications to browser PushManager subscriptions. It is **complementary**
to Telegram — see :mod:`ds_agent.domain.notification.push_policy` for the
encoded ADR (only APPROVAL and ERROR are eligible).

Clean Architecture
------------------
This use case depends only on:
  * the domain push-eligibility predicate (pure)
  * two output port Protocols defined right here

Concrete adapters (HTTP transport, JSON store) live in
:mod:`ds_agent.infrastructure` and inject themselves via the composition
root, not the other way around.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ds_agent.domain.notification import (
    Notification,
    is_push_eligible,
)

# ---------------------------------------------------------------------------
# Output ports
# ---------------------------------------------------------------------------


class WebPushSubscription(Protocol):
    """Read-only shape of a stored web push subscription.

    Kept as a structural Protocol so the application layer does NOT depend
    on the concrete dataclass living in infrastructure. Any object with
    these three attributes is acceptable.
    """

    @property
    def endpoint(self) -> str: ...
    @property
    def p256dh_key(self) -> str: ...
    @property
    def auth_key(self) -> str: ...


class WebPushTransportPort(Protocol):
    """Output port the use case calls to actually deliver a push payload."""

    def deliver(
        self,
        *,
        operator_id: str,
        subscription: WebPushSubscription,
        notification: Notification,
    ) -> str:
        """Send *notification* to *subscription* and return a transport id.

        ``operator_id`` is threaded so the transport adapter can invoke
        prune callbacks keyed by ``(operator_id, endpoint)`` when the
        push gateway reports an expired subscription (HTTP 404 / 410).
        """


class WebPushSubscriptionStorePort(Protocol):
    """Output port for loading active push subscriptions per operator."""

    def list_for(self, operator_id: str) -> list[WebPushSubscription]:
        """Return the currently registered subscriptions for an operator."""


# ---------------------------------------------------------------------------
# Result DTO
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DispatchWebPushResult:
    """Outcome of one push fan-out attempt.

    *delivered_count* is the number of subscriptions the transport
    accepted. *pruned_count* counts subscriptions auto-removed because
    the push gateway reported them expired (HTTP 404 / 410) — those
    failures are *not* errors, they are routine cleanup and are excluded
    from ``skipped_reason`` triggering. *skipped_reason* is set only
    when the use case fully short-circuits (ineligible category, no
    subscriptions, or the transport itself is unavailable).
    """

    delivered_count: int
    skipped_reason: str | None
    pruned_count: int = 0


# Stable skip-reason tokens. Defined as module-level constants so callers
# (tests, telemetry) can match without typo risk.
SKIP_NOT_ELIGIBLE = "category_not_push_eligible"
SKIP_NO_SUBSCRIPTIONS = "no_active_subscriptions"
SKIP_TRANSPORT_UNAVAILABLE = "transport_unavailable"


class WebPushTransportUnavailableError(Exception):
    """Raised by the transport adapter when push cannot be sent at all.

    The use case treats this as a soft skip with
    :data:`SKIP_TRANSPORT_UNAVAILABLE` so a missing VAPID key in the
    environment never crashes the surrounding notification pipeline.
    """


class WebPushSubscriptionExpiredError(Exception):
    """Raised by the transport when the push gateway reports the
    subscription has expired (HTTP 404 / 410 GONE).

    The transport SHOULD invoke its on-prune callback before raising so
    the caller can drop the subscription from the store. The use case
    treats this as a routine prune (counted in
    :attr:`DispatchWebPushResult.pruned_count`) — *not* a hard error.
    """


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------


class DispatchWebPushUseCase:
    """Fan out *notification* to every registered push subscription.

    Order of checks (each can short-circuit with a stable skip reason):

    1. Domain predicate: is the category push-eligible?
    2. Store: are there any active subscriptions for the operator?
    3. Transport: is push actually wired (VAPID key present, libs ok)?
    """

    def __init__(
        self,
        *,
        transport: WebPushTransportPort,
        subscription_store: WebPushSubscriptionStorePort,
    ) -> None:
        self._transport = transport
        self._store = subscription_store

    def execute(
        self,
        *,
        operator_id: str,
        notification: Notification,
    ) -> DispatchWebPushResult:
        if not is_push_eligible(notification.category):
            return DispatchWebPushResult(
                delivered_count=0,
                skipped_reason=SKIP_NOT_ELIGIBLE,
            )

        subscriptions = list(self._store.list_for(operator_id))
        if not subscriptions:
            return DispatchWebPushResult(
                delivered_count=0,
                skipped_reason=SKIP_NO_SUBSCRIPTIONS,
            )

        delivered = 0
        pruned = 0
        for subscription in subscriptions:
            try:
                self._transport.deliver(
                    operator_id=operator_id,
                    subscription=subscription,
                    notification=notification,
                )
                delivered += 1
            except WebPushSubscriptionExpiredError:
                # Routine prune — the transport adapter has already
                # invoked its on-prune callback; just keep the loop going
                # so siblings still receive the push.
                pruned += 1
                continue
            except WebPushTransportUnavailableError:
                return DispatchWebPushResult(
                    delivered_count=delivered,
                    skipped_reason=SKIP_TRANSPORT_UNAVAILABLE,
                    pruned_count=pruned,
                )

        return DispatchWebPushResult(
            delivered_count=delivered,
            skipped_reason=None,
            pruned_count=pruned,
        )


__all__ = [
    "SKIP_NOT_ELIGIBLE",
    "SKIP_NO_SUBSCRIPTIONS",
    "SKIP_TRANSPORT_UNAVAILABLE",
    "DispatchWebPushResult",
    "DispatchWebPushUseCase",
    "WebPushSubscription",
    "WebPushSubscriptionExpiredError",
    "WebPushSubscriptionStorePort",
    "WebPushTransportPort",
    "WebPushTransportUnavailableError",
]
