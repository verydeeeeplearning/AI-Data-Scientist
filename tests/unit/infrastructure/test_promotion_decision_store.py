from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.domain.entities.promotion import PromotionDecision
from ds_agent.infrastructure.persistence.promotion_decision_store import (
    SqlitePromotionDecisionStore,
)


def _decision() -> PromotionDecision:
    return PromotionDecision.model_validate(
        {
            "decision_id": "decision-001",
            "candidate_run_id": "run-candidate",
            "candidate_model_id": "m_churn_lightgbm",
            "target_stage": "production",
            "policy_checks": [
                {
                    "name": "verifier_pass",
                    "status": "pass",
                    "detail": "All verifier categories passed.",
                }
            ],
            "approvals": [
                {"role": "DS", "approver": "ds-user", "status": "pending"},
                {"role": "Lead", "approver": "lead-user", "status": "pending"},
                {"role": "MLOps", "approver": "mlops-user", "status": "pending"},
            ],
            "chain_state": "pending_DS",
            "rollback_plan_ref": "rollback_plan.yaml",
            "created_at": datetime(2026, 4, 16, tzinfo=UTC),
        }
    )


def test_sqlite_promotion_decision_store_round_trips_and_updates(tmp_path) -> None:
    store = SqlitePromotionDecisionStore(tmp_path / "promotion_gate.db")
    decision = _decision()

    store.save(decision)
    loaded = store.get(decision.decision_id)

    assert loaded is not None
    assert loaded.chain_state == "pending_DS"
    assert loaded.approvals[0].status == "pending"

    updated = loaded.model_copy(
        update={
            "chain_state": "pending_Lead",
            "approvals": [
                loaded.approvals[0].model_copy(
                    update={
                        "status": "approved",
                        "decided_at": datetime(2026, 4, 16, 1, tzinfo=UTC),
                        "note": "Looks good.",
                    }
                ),
                *loaded.approvals[1:],
            ],
        }
    )
    store.save(updated)

    reloaded = store.get(decision.decision_id)
    assert reloaded is not None
    assert reloaded.chain_state == "pending_Lead"
    assert reloaded.approvals[0].status == "approved"

    by_model = store.list_for_model("m_churn_lightgbm")
    assert [item.decision_id for item in by_model] == ["decision-001"]
