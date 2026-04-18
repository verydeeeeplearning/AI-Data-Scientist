"""Tests for ds_agent.runtime.delivery_settings."""

from __future__ import annotations

from ds_agent.runtime.delivery_policy_store import DeliveryPolicy
from ds_agent.runtime.delivery_settings import resolve_effective_delivery_settings
from ds_agent.runtime.operator_preferences_store import ChatPreference


class TestResolveEffectiveDeliverySettings:
    def test_pref_digest_overrides_global_defaults(self) -> None:
        pref = ChatPreference(
            chat_id="chat1",
            digest_mode=True,
            digest_cadence="morning",
            digest_interval_seconds=1800.0,
            timezone="Asia/Seoul",
        )
        policy = DeliveryPolicy(
            digest_enabled=False,
            digest_interval_seconds=900.0,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            quiet_hours_timezone="UTC",
        )

        resolved = resolve_effective_delivery_settings(pref, policy)

        assert resolved.digest_enabled is True
        assert resolved.digest_cadence == "morning"
        assert resolved.digest_interval_seconds == 1800.0
        assert resolved.timezone == "Asia/Seoul"
        assert resolved.quiet_hours.timezone == "Asia/Seoul"

    def test_global_digest_applies_when_chat_has_no_override(self) -> None:
        pref = ChatPreference(chat_id="chat1", digest_mode=False, timezone="")
        policy = DeliveryPolicy(
            digest_enabled=True,
            digest_interval_seconds=1200.0,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            quiet_hours_timezone="UTC",
        )

        resolved = resolve_effective_delivery_settings(pref, policy)

        assert resolved.digest_enabled is True
        assert resolved.digest_cadence == "interval"
        assert resolved.digest_interval_seconds == 1200.0
        assert resolved.timezone == "UTC"
