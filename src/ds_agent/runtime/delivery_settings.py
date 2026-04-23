"""Resolve effective delivery behavior from global policy and chat preference."""

from __future__ import annotations

from dataclasses import dataclass

from ds_agent.runtime.delivery_policy_store import DeliveryPolicy
from ds_agent.runtime.delivery_rate_limiter import QuietHoursWindow
from ds_agent.runtime.operator_preferences_store import (
    ChatPreference,
    normalize_digest_cadence,
)


@dataclass(frozen=True, slots=True)
class EffectiveDeliverySettings:
    """Merged delivery view for one operator chat."""

    chat_id: str
    enabled: bool
    min_severity: str
    subscribed_categories: set[str]
    approvals_only: bool
    live_push_enabled: bool
    escalation_enabled: bool
    artifact_auto_delivery_enabled: bool
    digest_enabled: bool
    digest_cadence: str
    digest_interval_seconds: float
    timezone: str
    quiet_hours: QuietHoursWindow


def resolve_effective_delivery_settings(
    preference: ChatPreference,
    policy: DeliveryPolicy,
) -> EffectiveDeliverySettings:
    """Combine chat preference with policy defaults into one effective view."""
    timezone = preference.timezone.strip() or policy.quiet_hours_timezone or "UTC"
    digest_cadence = "interval"
    digest_interval_seconds = max(60.0, policy.digest_interval_seconds)
    digest_enabled = policy.digest_enabled

    if preference.digest_mode:
        digest_enabled = True
        digest_interval_seconds = max(60.0, preference.digest_interval_seconds)
        digest_cadence = normalize_digest_cadence(preference.digest_cadence) or "interval"

    return EffectiveDeliverySettings(
        chat_id=preference.chat_id,
        enabled=preference.enabled,
        min_severity=preference.min_severity,
        subscribed_categories=set(preference.subscribed_categories),
        approvals_only=preference.approvals_only,
        live_push_enabled=policy.live_push_enabled,
        escalation_enabled=policy.escalation_enabled,
        artifact_auto_delivery_enabled=policy.artifact_auto_delivery_enabled,
        digest_enabled=digest_enabled,
        digest_cadence=digest_cadence,
        digest_interval_seconds=digest_interval_seconds,
        timezone=timezone,
        quiet_hours=_quiet_hours_window(
            policy.quiet_hours_start,
            policy.quiet_hours_end,
            timezone,
        ),
    )


def _quiet_hours_window(
    start_text: str,
    end_text: str,
    timezone: str,
) -> QuietHoursWindow:
    start_hour = _parse_quiet_hour(start_text)
    end_hour = _parse_quiet_hour(end_text)
    if start_hour is None or end_hour is None:
        return QuietHoursWindow()
    return QuietHoursWindow(
        start_hour=start_hour,
        end_hour=end_hour,
        timezone=timezone,
        enabled=True,
    )


def _parse_quiet_hour(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    try:
        hour_text, *_rest = text.split(":", maxsplit=1)
        hour = int(hour_text)
    except ValueError:
        return None
    if 0 <= hour <= 23:
        return hour
    return None
