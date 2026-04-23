from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.application.use_cases.check_quiet_hours_usecase import (
    CheckQuietHoursUseCase,
    QuietHoursPolicyPort,
)
from ds_agent.application.use_cases.send_notification_usecase import (
    NotificationTransportPort,
    SendNotificationUseCase,
)
from ds_agent.domain.notification import (
    Notification,
    NotificationCategory,
    QuietHours,
    QuietHoursPolicy,
)
from ds_agent.runtime.deferred_notification_store import JsonDeferredNotificationStore


class _FixedPolicyPort(QuietHoursPolicyPort):
    def __init__(self, policy: QuietHoursPolicy) -> None:
        self._policy = policy

    def load(self, *, operator_id: str) -> QuietHoursPolicy:
        return self._policy


class _RecordingTransport(NotificationTransportPort):
    def __init__(self) -> None:
        self.delivered: list[tuple[str, Notification]] = []

    def deliver(self, *, operator_id: str, notification: Notification) -> str:
        self.delivered.append((operator_id, notification))
        return "transport-1"


def test_quiet_hours_deferred_notifications_persist_across_store_reload(tmp_path) -> None:
    store = JsonDeferredNotificationStore(base_dir=tmp_path)
    quiet_hours = CheckQuietHoursUseCase(
        _FixedPolicyPort(
            QuietHoursPolicy(window=QuietHours(timezone_name="UTC", start_hour=22, end_hour=7))
        )
    )
    transport = _RecordingTransport()
    use_case = SendNotificationUseCase(
        transport=transport,
        quiet_hours=quiet_hours,
        deferred_store=store,
    )
    now = datetime(2026, 4, 20, 23, 15, tzinfo=UTC)

    result = use_case.execute(
        operator_id="op-quiet",
        notification=Notification(
            category=NotificationCategory.MILESTONE,
            title="training complete",
            body="validation improved by 2.1pp",
            workspace_id="workspace-99",
            run_id="run-42",
        ),
        now=now,
    )

    assert result.delivered is False
    assert result.deferred is True
    assert transport.delivered == []

    reloaded = JsonDeferredNotificationStore(base_dir=tmp_path)
    parked = reloaded.list_parked("op-quiet")

    assert len(parked) == 1
    assert parked[0].deferred_at == now
    assert parked[0].notification.category is NotificationCategory.MILESTONE
    assert parked[0].notification.title == "training complete"
    assert parked[0].notification.workspace_id == "workspace-99"
    assert parked[0].notification.run_id == "run-42"
