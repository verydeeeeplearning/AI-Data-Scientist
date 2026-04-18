from datetime import UTC, datetime

from ds_agent.domain.entities.assumption_log import AssumptionEntry


def test_high_risk_assumption_defaults_to_unverified() -> None:
    entry = AssumptionEntry(
        entry_id="AS-1",
        statement="Churn means 30 days inactive",
        rationale="Current retention team convention",
        risk_level="high",
        created_at=datetime(2026, 4, 15, tzinfo=UTC),
    )
    assert entry.verified is False
    assert entry.asked_user is False
