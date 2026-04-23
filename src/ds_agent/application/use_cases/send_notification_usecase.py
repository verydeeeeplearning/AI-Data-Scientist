"""Use case: dispatch a notification to a transport.

Coordinates quiet-hours suppression with delivery.  Knows nothing about
Telegram specifics — the transport port is implemented by the channel
adapter (e.g. message_builder + telegram plugin).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ds_agent.application.use_cases.check_quiet_hours_usecase import (
    CheckQuietHoursUseCase,
)
from ds_agent.domain.notification import Notification


class NotificationTransportPort(Protocol):
    """Output port the use case calls to actually deliver a notification."""

    def deliver(
        self,
        *,
        operator_id: str,
        notification: Notification,
    ) -> str: ...


class DeferredNotificationStorePort(Protocol):
    """Output port for parking quiet-hours-suppressed notifications."""

    def park(
        self,
        *,
        operator_id: str,
        notification: Notification,
        deferred_at: datetime,
    ) -> None: ...


@dataclass(slots=True)
class SendNotificationResult:
    delivered: bool
    deferred: bool
    transport_id: str | None
    reason: str


class SendNotificationUseCase:
    """Dispatch *notification* respecting the operator's quiet-hours policy."""

    def __init__(
        self,
        *,
        transport: NotificationTransportPort,
        quiet_hours: CheckQuietHoursUseCase,
        deferred_store: DeferredNotificationStorePort | None = None,
    ) -> None:
        self._transport = transport
        self._quiet_hours = quiet_hours
        self._deferred_store = deferred_store

    def execute(
        self,
        *,
        operator_id: str,
        notification: Notification,
        now: datetime | None = None,
    ) -> SendNotificationResult:
        decision = self._quiet_hours.execute(
            operator_id=operator_id,
            notification=notification,
            now=now,
        )
        if decision.suppress:
            if self._deferred_store is not None and now is not None:
                self._deferred_store.park(
                    operator_id=operator_id,
                    notification=notification,
                    deferred_at=now,
                )
            return SendNotificationResult(
                delivered=False,
                deferred=True,
                transport_id=None,
                reason=decision.reason,
            )

        transport_id = self._transport.deliver(
            operator_id=operator_id,
            notification=notification,
        )
        return SendNotificationResult(
            delivered=True,
            deferred=False,
            transport_id=transport_id,
            reason=decision.reason,
        )
