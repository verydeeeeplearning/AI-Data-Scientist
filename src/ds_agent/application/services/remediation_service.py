"""Operational remediation decisions for PLAN 17 Phase 5."""

from __future__ import annotations

from ds_agent.domain.value_objects.remediation import RemediationDecision


class RemediationService:
    """Choose retrain, rollback, or no-action from drift and performance."""

    def decide(self, drift_score: float, performance_delta: float) -> RemediationDecision:
        """Return a remediation decision."""
        if performance_delta <= -0.10:
            return RemediationDecision(
                decision="rollback",
                severity="critical",
                rationale="Performance dropped more than 10% versus the baseline.",
                should_alert=True,
                recommended_steps=[
                    "Rollback to the last stable model.",
                    "Open an incident and review recent data and deployment changes.",
                ],
            )

        if drift_score > 0.20:
            return RemediationDecision(
                decision="retrain",
                severity="high",
                rationale="Input drift exceeded the operational danger threshold.",
                should_alert=True,
                recommended_steps=[
                    "Retrain with the latest representative data.",
                    "Review whether feature definitions changed upstream.",
                ],
            )

        if 0.10 <= drift_score <= 0.20 and performance_delta <= -0.05:
            return RemediationDecision(
                decision="retrain",
                severity="medium",
                rationale="Moderate drift combined with a material performance drop.",
                should_alert=True,
                recommended_steps=[
                    "Schedule retraining.",
                    "Compare feature importances before and after retraining.",
                ],
            )

        if drift_score < 0.10 and performance_delta <= -0.05:
            return RemediationDecision(
                decision="monitor",
                severity="medium",
                rationale="Performance worsened but drift is limited, so monitor before acting.",
                should_alert=False,
                recommended_steps=[
                    "Monitor the next few batches.",
                    "Check labeling latency and upstream data quality.",
                ],
            )

        return RemediationDecision(
            decision="no_action",
            severity="low",
            rationale="Observed movement is within expected operational noise.",
            should_alert=False,
            recommended_steps=["Keep monitoring on the normal cadence."],
        )

    @staticmethod
    def build_trigger_payload(
        decision: RemediationDecision,
        *,
        model_id: str,
    ) -> dict[str, object]:
        """Build a machine-readable trigger payload."""
        trigger = decision.decision if decision.decision in {"retrain", "rollback"} else "monitor"
        return {
            "trigger": trigger,
            "model_id": model_id,
            "severity": decision.severity,
            "should_alert": decision.should_alert,
            "steps": decision.recommended_steps,
        }
