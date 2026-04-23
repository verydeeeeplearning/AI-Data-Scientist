"""Integration test: TelegramGatewayRunner persists quiet-hours deferrals.

Wires the production composition (the same code path
``TelegramGatewayRunner.__init__`` runs) and asserts that a notification
suppressed during quiet hours is durably persisted via
:class:`JsonDeferredNotificationStore`, and that a fresh runner sees the
same parked record after a simulated restart.
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
)
from ds_agent.gateway.telegram_runner import (
    TelegramGatewayRunner,
    _DeliveryPolicyQuietHoursPort,
    _NullNotificationTransport,
)
from ds_agent.runtime.deferred_notification_store import JsonDeferredNotificationStore
from ds_agent.runtime.delivery_policy_store import DeliveryPolicy, JsonDeliveryPolicyStore


def _wire_runner(workspace_dir, *, quiet_hours: tuple[str, str, str]) -> TelegramGatewayRunner:
    """Reproduce the live composition `__init__` performs.

    Only the fields ``dispatch_notification`` actually touches are wired,
    matching the production path (``JsonDeferredNotificationStore`` rooted
    at the workspace + ``SendNotificationUseCase`` reading quiet-hours
    from :class:`JsonDeliveryPolicyStore`).
    """
    runner = TelegramGatewayRunner.__new__(TelegramGatewayRunner)
    runner._plugin = MagicMock()
    runner._plugin.send_text = AsyncMock()
    runner._delivery_targets = {}
    runner._message_builder = TelegramMessageBuilder()

    # Same JsonDeliveryPolicyStore the runner __init__ builds.
    delivery_policy_store = JsonDeliveryPolicyStore(workspace_dir)
    start, end, tz = quiet_hours
    delivery_policy_store.update(
        DeliveryPolicy(
            quiet_hours_start=start,
            quiet_hours_end=end,
            quiet_hours_timezone=tz,
        )
    )
    runner._delivery_policy_store = delivery_policy_store

    # Same wiring the runner __init__ does.
    runner._deferred_notification_store = JsonDeferredNotificationStore(
        str(workspace_dir)
    )
    runner._send_notification_use_case = SendNotificationUseCase(
        transport=_NullNotificationTransport(),
        quiet_hours=CheckQuietHoursUseCase(
            _DeliveryPolicyQuietHoursPort(runner._delivery_policy_store)
        ),
        deferred_store=runner._deferred_notification_store,
    )
    return runner


@pytest.mark.asyncio
async def test_quiet_hours_dispatch_persists_and_survives_restart(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # 0..23 == every hour is quiet, ensures suppression regardless of
    # wall-clock at the moment dispatch_notification calls datetime.now.
    runner = _wire_runner(workspace, quiet_hours=("0", "23", "UTC"))

    notification = Notification(
        category=NotificationCategory.MILESTONE,
        title="training complete",
        body="validation improved by 2.1pp",
        workspace_id="workspace-99",
        run_id="run-42",
    )

    await runner.dispatch_notification(notification, "telegram-chat-1")

    # Live transport must NOT have been invoked because quiet hours
    # suppressed the notification.
    runner._plugin.send_text.assert_not_awaited()

    # Restart: a fresh JsonDeferredNotificationStore rooted at the same
    # workspace must see the same parked record.
    reloaded = JsonDeferredNotificationStore(str(workspace))
    parked = reloaded.list_parked("telegram-chat-1")
    assert len(parked) == 1
    assert parked[0].notification.title == "training complete"
    assert parked[0].notification.workspace_id == "workspace-99"
    assert parked[0].notification.run_id == "run-42"
    assert parked[0].notification.category is NotificationCategory.MILESTONE


@pytest.mark.asyncio
async def test_outside_quiet_hours_dispatch_actually_sends(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # No quiet-hours window configured (empty strings) → port reports
    # window disabled → use case never defers.
    runner = _wire_runner(workspace, quiet_hours=("", "", "UTC"))

    notification = Notification(
        category=NotificationCategory.MILESTONE,
        title="training complete",
        body="validation improved by 2.1pp",
        workspace_id="workspace-99",
        run_id="run-42",
    )

    await runner.dispatch_notification(notification, "telegram-chat-2")

    # Delivered for real — live transport called once.
    runner._plugin.send_text.assert_awaited_once()
    # And nothing should be parked on disk.
    parked = JsonDeferredNotificationStore(str(workspace)).list_parked(
        "telegram-chat-2"
    )
    assert parked == []


@pytest.mark.asyncio
async def test_approval_bypasses_quiet_hours_and_sends_live(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Always-quiet window — but APPROVAL bypasses quiet hours per
    # NotificationCategory.bypasses_quiet_hours, so it must still be sent.
    runner = _wire_runner(workspace, quiet_hours=("0", "23", "UTC"))

    notification = Notification(
        category=NotificationCategory.APPROVAL,
        title="manual approval",
        body="continue?",
    )

    await runner.dispatch_notification(notification, "telegram-chat-3")

    runner._plugin.send_text.assert_awaited_once()
    parked = JsonDeferredNotificationStore(str(workspace)).list_parked(
        "telegram-chat-3"
    )
    assert parked == []
