"""Tests for ds_agent.runtime.delivery_rate_limiter."""

from __future__ import annotations

from ds_agent.runtime.delivery_rate_limiter import (
    DeliveryRateLimiter,
    QuietHoursWindow,
)


class TestDeliveryRateLimiter:
    def test_default_allows_delivery(self) -> None:
        limiter = DeliveryRateLimiter()
        assert limiter.should_deliver("recovery.resume", "warning")

    def test_cooldown_blocks_repeat(self) -> None:
        limiter = DeliveryRateLimiter()
        assert limiter.should_deliver("recovery.resume", "warning")
        assert not limiter.should_deliver("recovery.resume", "warning")

    def test_escalation_bypasses_quiet_hours(self) -> None:
        limiter = DeliveryRateLimiter(
            quiet_hours=QuietHoursWindow(start_hour=0, end_hour=24, enabled=True)
        )
        assert not limiter.should_deliver("health.check", "warning")
        assert limiter.should_deliver("health.check", "warning", is_escalation=True)

    def test_critical_bypasses_quiet_hours(self) -> None:
        limiter = DeliveryRateLimiter(
            quiet_hours=QuietHoursWindow(start_hour=0, end_hour=24, enabled=True)
        )
        assert limiter.should_deliver("health.check", "critical")

    def test_escalation_after_repeated_failures(self) -> None:
        limiter = DeliveryRateLimiter(escalation_threshold=3)
        assert not limiter.record_failure("pipeline_x")
        assert not limiter.record_failure("pipeline_x")
        assert limiter.record_failure("pipeline_x")

    def test_reset_failure_counter(self) -> None:
        limiter = DeliveryRateLimiter(escalation_threshold=2)
        limiter.record_failure("key1")
        limiter.reset_failure("key1")
        assert not limiter.record_failure("key1")

    def test_quiet_hours_disabled_by_default(self) -> None:
        limiter = DeliveryRateLimiter()
        assert not limiter.is_in_quiet_hours()
