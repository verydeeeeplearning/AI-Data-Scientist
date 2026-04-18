from datetime import UTC, datetime

import pytest

from ds_agent.domain.entities.certification import (
    CertificationRecord,
    CertificationSpec,
    CertificationStats,
)


def _spec_payload() -> dict[str, object]:
    return {
        "current_level": "delegate",
        "next_target": "autopilot",
        "autopilot_requirements": {
            "shadow_runs_passed": 10,
            "critical_violations": 0,
            "verifier_avg_score": 0.85,
            "rollback_rehearsal": "passed",
            "owner_approvals": 2,
        },
        "history": [
            {
                "date": "2026-03-20",
                "level": "supervised -> delegate",
                "approved_by": "owner-cho",
                "evidence_ref": "certification/ev-2026-03-20.md",
            }
        ],
        "next_review": "2026-06-01",
    }


def test_certification_spec_evaluates_unmet_requirements() -> None:
    spec = CertificationSpec.model_validate(_spec_payload())
    stats = CertificationStats(
        shadow_runs_passed=8,
        critical_violations=1,
        verifier_avg_score=0.81,
        rollback_rehearsal_passed=False,
    )

    gaps = spec.evaluate("autopilot", stats)

    assert "shadow_runs_passed 8/10" in gaps
    assert "critical_violations 1>0" in gaps
    assert "verifier_avg_score 0.81<0.85" in gaps
    assert "rollback_rehearsal not passed" in gaps
    assert spec.is_certified_for("delegate") is True
    assert spec.is_certified_for("autopilot") is False


def test_certification_record_requires_at_least_one_approver() -> None:
    with pytest.raises(ValueError):
        CertificationRecord(
            mission_name="weekly-kpi-triage",
            mission_version=1,
            level="autopilot",
            approved_by=(),
            approved_at=datetime(2026, 4, 16, tzinfo=UTC),
        )
