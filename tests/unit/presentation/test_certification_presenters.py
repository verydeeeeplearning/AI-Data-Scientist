from datetime import UTC, datetime

from ds_agent.application.services.certification_usecases import (
    CertificationStatusResult,
    SubmitCertificationResult,
)
from ds_agent.domain.entities.certification import CertificationRecord, CertificationStats
from ds_agent.domain.value_objects.authority_mode import AuthorityMode


def test_render_certification_status_includes_levels_and_gaps() -> None:
    from ds_agent.presentation.certification_presenters import render_certification_status

    text = render_certification_status(
        CertificationStatusResult(
            mission_name="weekly-kpi-triage",
            mission_version=1,
            current_level=AuthorityMode.DELEGATE,
            effective_level=AuthorityMode.DELEGATE,
            next_target=AuthorityMode.AUTOPILOT,
            required_approvers=2,
            certified_for_next_target=False,
            gaps=("shadow_runs_passed 8/10", "rollback_rehearsal not passed"),
            stats=CertificationStats(
                shadow_runs_passed=8,
                critical_violations=0,
                verifier_avg_score=0.84,
                rollback_rehearsal_passed=False,
            ),
        )
    )

    assert "Certification: weekly-kpi-triage v1" in text
    assert "current=delegate" in text
    assert "not certified" in text
    assert "shadow_runs_passed 8/10" in text


def test_render_certification_submission_includes_approval_summary() -> None:
    from ds_agent.presentation.certification_presenters import render_certification_submission

    text = render_certification_submission(
        SubmitCertificationResult(
            mission_name="weekly-kpi-triage",
            mission_version=1,
            target_level=AuthorityMode.AUTOPILOT,
            status="certified",
            current_level=AuthorityMode.DELEGATE,
            required_approvers=2,
            approved_by=("owner-park", "owner-cho"),
            gaps=(),
            stats=CertificationStats(),
            certification=CertificationRecord(
                mission_name="weekly-kpi-triage",
                mission_version=1,
                level=AuthorityMode.AUTOPILOT,
                transition_from=AuthorityMode.DELEGATE,
                approved_by=("owner-park", "owner-cho"),
                approved_at=datetime(2026, 4, 16, tzinfo=UTC),
            ),
        )
    )

    assert "Certification submit: weekly-kpi-triage v1" in text
    assert "Status: certified" in text
    assert "Approved by: owner-park, owner-cho" in text
