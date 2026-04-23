"""Composition wiring contract: dispatch_notification + persistent deferred store.

Locks PLAN_04 sign-off: when dispatch_notification is asked to deliver while
quiet hours are active, the suppressed notification must reach disk via
JsonDeferredNotificationStore so it survives a process restart.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ds_agent.application.use_cases.check_quiet_hours_usecase import (
    CheckQuietHoursUseCase,
)
from ds_agent.application.use_cases.send_notification_usecase import (
    SendNotificationUseCase,
)
from ds_agent.channels.bundled.telegram.message_builder import TelegramMessageBuilder
from ds_agent.domain.notification import (
    Notification,
    NotificationCategory,
    QuietHoursPolicy,
)
from ds_agent.domain.notification.quiet_hours import QuietHours
from ds_agent.runtime.deferred_notification_store import (
    JsonDeferredNotificationStore,
)


class _AlwaysQuietPolicy:
    """Stub port: returns a policy whose window always contains *now*."""

    def load(self, *, operator_id: str) -> QuietHoursPolicy:
        return QuietHoursPolicy(
            window=QuietHours(start_hour=0, end_hour=0, enabled=True),
        )


class _NeverQuietPolicy:
    def load(self, *, operator_id: str) -> QuietHoursPolicy:
        return QuietHoursPolicy(
            window=QuietHours(start_hour=0, end_hour=0, enabled=False),
        )


def _make_runner_with_persistent_store(tmp_path, *, policy_port):
    """Mirror telegram_runner.__init__ lines 411-420 + dispatch path 3630-3651."""
    from ds_agent.gateway.telegram_runner import TelegramGatewayRunner

    runner = TelegramGatewayRunner.__new__(TelegramGatewayRunner)
    runner._plugin = MagicMock()
    runner._plugin.send_text = AsyncMock()
    runner._delivery_targets = {}
    runner._message_builder = TelegramMessageBuilder()

    store = JsonDeferredNotificationStore(str(tmp_path))
    runner._deferred_notification_store = store
    runner._send_notification_use_case = SendNotificationUseCase(
        transport=MagicMock(),
        quiet_hours=CheckQuietHoursUseCase(policy_port),
        deferred_store=store,
    )
    return runner, store


@pytest.mark.asyncio
async def test_dispatch_notification_persists_when_quiet_hours_active(tmp_path):
    runner, store = _make_runner_with_persistent_store(
        tmp_path, policy_port=_AlwaysQuietPolicy()
    )
    notification = Notification(
        category=NotificationCategory.INFO,
        title="run summary",
        body="...",
    )

    await runner.dispatch_notification(notification, conversation_id="op-42")

    parked = store.list_parked("op-42")
    assert len(parked) == 1
    assert parked[0].notification.title == "run summary"
    runner._plugin.send_text.assert_not_called()


@pytest.mark.asyncio
async def test_deferred_records_survive_store_restart(tmp_path):
    """A fresh store reading the same path must see prior parks."""
    runner, _store = _make_runner_with_persistent_store(
        tmp_path, policy_port=_AlwaysQuietPolicy()
    )
    notification = Notification(
        category=NotificationCategory.MILESTONE,
        title="schedule trigger",
        body="...",
    )
    await runner.dispatch_notification(notification, conversation_id="op-7")

    fresh = JsonDeferredNotificationStore(str(tmp_path))
    parked = fresh.list_parked("op-7")
    assert len(parked) == 1
    assert parked[0].notification.title == "schedule trigger"


@pytest.mark.asyncio
async def test_digest_category_bypasses_persistence_short_circuit(tmp_path):
    """DIGEST is the release mechanism; dispatch must short-circuit before suppression."""
    runner, store = _make_runner_with_persistent_store(
        tmp_path, policy_port=_AlwaysQuietPolicy()
    )
    notification = Notification(
        category=NotificationCategory.DIGEST,
        title="quiet-hours digest",
        body="...",
    )
    await runner.dispatch_notification(notification, conversation_id="op-1")

    assert store.list_parked("op-1") == []
    runner._plugin.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_notification_delivers_when_not_quiet(tmp_path):
    runner, store = _make_runner_with_persistent_store(
        tmp_path, policy_port=_NeverQuietPolicy()
    )
    notification = Notification(
        category=NotificationCategory.INFO,
        title="live alert",
        body="...",
    )

    await runner.dispatch_notification(notification, conversation_id="op-9")

    assert store.list_parked("op-9") == []
    runner._plugin.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_error_category_bypasses_quiet_hours(tmp_path):
    """ERROR must always reach the operator, even when policy is always-quiet."""
    runner, store = _make_runner_with_persistent_store(
        tmp_path, policy_port=_AlwaysQuietPolicy()
    )
    notification = Notification(
        category=NotificationCategory.ERROR,
        title="urgent",
        body="...",
    )
    await runner.dispatch_notification(notification, conversation_id="op-2")

    assert store.list_parked("op-2") == []
    runner._plugin.send_text.assert_called_once()
