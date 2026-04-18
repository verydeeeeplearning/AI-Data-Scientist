"""Tests for ds_agent.runtime.event_classifier."""

from __future__ import annotations

from ds_agent.runtime.event_classifier import (
    DeliveryDecision,
    classify_event,
    evaluate_delivery,
)
from ds_agent.runtime.runtime_event_log import RuntimeEventRecord


def _make_event(
    kind: str = "recovery.resume_recommended",
    category: str = "recovery",
    severity: str = "warning",
) -> RuntimeEventRecord:
    return RuntimeEventRecord(
        event_id="evt-1",
        category=category,
        kind=kind,
        severity=severity,
        message="test",
        session_id="s1",
        run_id=None,
        surface="daemon",
        source="test",
        metadata={},
        created_at=0.0,
    )


class TestClassifyEvent:
    def test_immediate_urgency(self) -> None:
        evt = _make_event(kind="recovery.awaiting_approval", severity="warning")
        c = classify_event(evt)
        assert c.urgency == "immediate"
        assert c.actionable is True

    def test_low_urgency_suppressible(self) -> None:
        evt = _make_event(kind="system.resource.normal", severity="info", category="health")
        c = classify_event(evt)
        assert c.urgency == "low"
        assert c.suppressible is True

    def test_normal_not_suppressible(self) -> None:
        evt = _make_event(kind="recovery.resume_recommended", severity="error")
        c = classify_event(evt)
        assert c.suppressible is False


class TestEvaluateDelivery:
    def test_live_push_default(self) -> None:
        c = classify_event(_make_event(severity="warning"))
        assert evaluate_delivery(c) == DeliveryDecision.LIVE_PUSH

    def test_suppress_below_severity(self) -> None:
        c = classify_event(_make_event(severity="info"))
        assert evaluate_delivery(c, chat_min_severity="warning") == DeliveryDecision.SUPPRESS

    def test_escalate_critical_immediate(self) -> None:
        c = classify_event(
            _make_event(kind="pipeline.health.degraded", severity="critical", category="health")
        )
        assert evaluate_delivery(c) == DeliveryDecision.ESCALATE

    def test_approvals_only_blocks_health(self) -> None:
        c = classify_event(_make_event(category="health", severity="warning"))
        assert evaluate_delivery(c, chat_approvals_only=True) == DeliveryDecision.SUPPRESS

    def test_approvals_only_passes_approval(self) -> None:
        c = classify_event(_make_event(category="approval", severity="warning"))
        assert evaluate_delivery(c, chat_approvals_only=True) == DeliveryDecision.LIVE_PUSH

    def test_mute_blocks_non_critical(self) -> None:
        c = classify_event(_make_event(severity="warning"))
        assert evaluate_delivery(c, chat_muted=True) == DeliveryDecision.SUPPRESS

    def test_mute_passes_critical(self) -> None:
        c = classify_event(
            _make_event(kind="pipeline.health.degraded", severity="critical", category="health")
        )
        assert evaluate_delivery(c, chat_muted=True) == DeliveryDecision.ESCALATE

    def test_digest_mode_for_suppressible(self) -> None:
        c = classify_event(
            _make_event(kind="system.resource.normal", severity="info", category="health")
        )
        assert (
            evaluate_delivery(
                c,
                chat_digest_mode=True,
                chat_min_severity="info",
            )
            == DeliveryDecision.DIGEST_ONLY
        )

    def test_digest_mode_buffers_non_immediate_recovery(self) -> None:
        c = classify_event(_make_event(kind="recovery.resume_recommended", severity="warning"))
        assert evaluate_delivery(c, chat_digest_mode=True) == DeliveryDecision.DIGEST_ONLY

    def test_category_filter(self) -> None:
        c = classify_event(_make_event(category="health", severity="warning"))
        assert (
            evaluate_delivery(c, chat_subscribed_categories={"approval"})
            == DeliveryDecision.SUPPRESS
        )

    def test_disabled_chat(self) -> None:
        c = classify_event(_make_event(severity="critical"))
        assert evaluate_delivery(c, chat_enabled=False) == DeliveryDecision.SUPPRESS
