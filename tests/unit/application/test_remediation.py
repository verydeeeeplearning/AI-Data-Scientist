"""Retrain vs rollback decision tests for PLAN 17 Phase 5."""

from __future__ import annotations

from ds_agent.application.services.remediation_service import RemediationService


class TestRemediationService:
    def test_recommends_retrain_for_high_drift(self):
        service = RemediationService()

        decision = service.decide(drift_score=0.25, performance_delta=-0.05)

        assert decision.decision == "retrain"
        assert decision.should_alert is True

    def test_recommends_no_action_for_small_noise(self):
        service = RemediationService()

        decision = service.decide(drift_score=0.05, performance_delta=-0.02)

        assert decision.decision == "no_action"

    def test_recommends_rollback_for_large_perf_drop(self):
        service = RemediationService()

        decision = service.decide(drift_score=0.03, performance_delta=-0.20)

        assert decision.decision == "rollback"
        assert decision.should_alert is True

    def test_builds_retrain_trigger_payload(self):
        service = RemediationService()

        decision = service.decide(drift_score=0.22, performance_delta=-0.06)
        payload = service.build_trigger_payload(decision, model_id="churn-v3")

        assert payload["trigger"] == "retrain"
        assert payload["model_id"] == "churn-v3"
