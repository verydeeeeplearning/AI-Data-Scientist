"""Tests for SendNotificationUseCase + CheckQuietHoursUseCase + BuildDigest."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ds_agent.application.use_cases.build_digest_usecase import (
    BuildDigestUseCase,
    DigestEntrySourcePort,
)
from ds_agent.application.use_cases.check_quiet_hours_usecase import (
    CheckQuietHoursUseCase,
    QuietHoursPolicyPort,
)
from ds_agent.application.use_cases.send_notification_usecase import (
    DeferredNotificationStorePort,
    NotificationTransportPort,
    SendNotificationUseCase,
)
from ds_agent.domain.notification import (
    DigestCadence,
    DigestEntry,
    Notification,
    NotificationCategory,
    QuietHours,
    QuietHoursPolicy,
)

_NOW_QUIET = datetime(2026, 4, 20, 23, 0, 0, tzinfo=UTC)
_NOW_AWAKE = datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC)


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
        return f"msg-{len(self.delivered)}"


class _RecordingDeferredStore(DeferredNotificationStorePort):
    def __init__(self) -> None:
        self.parked: list[tuple[str, Notification, datetime]] = []

    def park(
        self,
        *,
        operator_id: str,
        notification: Notification,
        deferred_at: datetime,
    ) -> None:
        self.parked.append((operator_id, notification, deferred_at))


def _info() -> Notification:
    return Notification(
        category=NotificationCategory.INFO,
        title="stage 3 done",
        body="b",
    )


def _approval() -> Notification:
    return Notification(
        category=NotificationCategory.APPROVAL,
        title="approve deploy",
        body="risk: medium",
    )


def _quiet_2200_to_0700() -> QuietHoursPolicy:
    return QuietHoursPolicy(
        window=QuietHours(timezone_name="UTC", start_hour=22, end_hour=7),
    )


def test_info_during_quiet_hours_is_deferred() -> None:
    transport = _RecordingTransport()
    store = _RecordingDeferredStore()
    quiet = CheckQuietHoursUseCase(_FixedPolicyPort(_quiet_2200_to_0700()))
    uc = SendNotificationUseCase(
        transport=transport, quiet_hours=quiet, deferred_store=store
    )

    result = uc.execute(operator_id="op1", notification=_info(), now=_NOW_QUIET)

    assert result.delivered is False
    assert result.deferred is True
    assert result.reason == "quiet_hours_active"
    assert transport.delivered == []
    assert len(store.parked) == 1
    assert store.parked[0][0] == "op1"


def test_info_outside_quiet_hours_is_delivered() -> None:
    transport = _RecordingTransport()
    quiet = CheckQuietHoursUseCase(_FixedPolicyPort(_quiet_2200_to_0700()))
    uc = SendNotificationUseCase(transport=transport, quiet_hours=quiet)

    result = uc.execute(operator_id="op1", notification=_info(), now=_NOW_AWAKE)

    assert result.delivered is True
    assert result.deferred is False
    assert result.transport_id == "msg-1"
    assert result.reason == "outside_window"


def test_approval_bypasses_quiet_hours() -> None:
    transport = _RecordingTransport()
    quiet = CheckQuietHoursUseCase(_FixedPolicyPort(_quiet_2200_to_0700()))
    uc = SendNotificationUseCase(transport=transport, quiet_hours=quiet)

    result = uc.execute(
        operator_id="op1", notification=_approval(), now=_NOW_QUIET
    )

    assert result.delivered is True
    assert result.reason == "bypass_category"
    assert len(transport.delivered) == 1


def test_error_bypasses_quiet_hours() -> None:
    transport = _RecordingTransport()
    quiet = CheckQuietHoursUseCase(_FixedPolicyPort(_quiet_2200_to_0700()))
    uc = SendNotificationUseCase(transport=transport, quiet_hours=quiet)

    err = Notification(
        category=NotificationCategory.ERROR, title="boom", body="b"
    )
    result = uc.execute(operator_id="op1", notification=err, now=_NOW_QUIET)
    assert result.delivered is True


def test_disabled_window_never_suppresses() -> None:
    transport = _RecordingTransport()
    policy = QuietHoursPolicy(window=QuietHours(enabled=False))
    quiet = CheckQuietHoursUseCase(_FixedPolicyPort(policy))
    uc = SendNotificationUseCase(transport=transport, quiet_hours=quiet)

    result = uc.execute(
        operator_id="op1", notification=_info(), now=_NOW_QUIET
    )
    assert result.delivered is True


# ---------------------------------------------------------------------------
# BuildDigest
# ---------------------------------------------------------------------------


class _StubSource(DigestEntrySourcePort):
    def __init__(self, entries: list[DigestEntry]) -> None:
        self._entries = entries
        self.calls: list[tuple[str, datetime, datetime]] = []

    def list_entries(
        self, *, operator_id: str, since: datetime, until: datetime
    ) -> list[DigestEntry]:
        self.calls.append((operator_id, since, until))
        return self._entries


def test_build_digest_passes_correct_window_to_source() -> None:
    source = _StubSource([])
    uc = BuildDigestUseCase(source)
    now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC)
    uc.execute(operator_id="op1", cadence=DigestCadence.DAILY, now=now)

    op_id, since, until = source.calls[0]
    assert op_id == "op1"
    assert until == now
    assert since == now - timedelta(days=1)


def test_build_digest_off_returns_empty_without_source_call() -> None:
    source = _StubSource([])
    uc = BuildDigestUseCase(source)
    now = datetime(2026, 4, 20, tzinfo=UTC)
    result = uc.execute(operator_id="op1", cadence=DigestCadence.OFF, now=now)

    assert result.digest.is_empty
    assert source.calls == []


def test_build_digest_aggregates_returned_entries() -> None:
    now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=UTC)
    entries = [
        DigestEntry(
            category=NotificationCategory.MILESTONE,
            title="m1",
            occurred_at=now - timedelta(hours=1),
        ),
        DigestEntry(
            category=NotificationCategory.ERROR,
            title="e1",
            occurred_at=now - timedelta(hours=2),
        ),
    ]
    source = _StubSource(entries)
    uc = BuildDigestUseCase(source)
    result = uc.execute(operator_id="op1", cadence=DigestCadence.DAILY, now=now)

    assert result.digest.total_count == 2
    assert result.digest.by_category[NotificationCategory.MILESTONE] == 1
    assert result.digest.by_category[NotificationCategory.ERROR] == 1
    assert result.operator_id == "op1"


def test_quiet_hours_decision_reasons() -> None:
    quiet = CheckQuietHoursUseCase(_FixedPolicyPort(_quiet_2200_to_0700()))

    bypass = quiet.execute(
        operator_id="op1", notification=_approval(), now=_NOW_QUIET
    )
    assert bypass.suppress is False
    assert bypass.reason == "bypass_category"

    suppressed = quiet.execute(
        operator_id="op1", notification=_info(), now=_NOW_QUIET
    )
    assert suppressed.suppress is True
    assert suppressed.reason == "quiet_hours_active"
