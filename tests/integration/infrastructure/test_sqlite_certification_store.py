from datetime import UTC, datetime

from ds_agent.domain.entities.certification import AutonomyRunStat, CertificationRecord
from ds_agent.infrastructure.persistence.certification_store import SqliteCertificationStore


def test_sqlite_certification_store_round_trip(tmp_path) -> None:
    store = SqliteCertificationStore(tmp_path / "autonomy_control_plane.db")
    for index in range(10):
        store.record_run_stat(
            AutonomyRunStat(
                mission_name="weekly-kpi-triage",
                mission_version=1,
                run_id=f"run-{index}",
                authority="shadow",
                audience="senior_staff",
                started_at=datetime(2026, 4, 1, tzinfo=UTC),
                ended_at=datetime(2026, 4, 1, tzinfo=UTC),
                outcome="success",
                verifier_score=0.90,
                rollback_rehearsal=index == 0,
            )
        )
    store.save_certification(
        CertificationRecord(
            mission_name="weekly-kpi-triage",
            mission_version=1,
            level="autopilot",
            transition_from="delegate",
            approved_by=("owner-park", "owner-cho"),
            approved_at=datetime(2026, 4, 16, tzinfo=UTC),
            evidence_ref="certification/ev-2026-04-16.md",
        )
    )

    stats = store.stats_for("weekly-kpi-triage", mission_version=1)
    latest = store.latest_certification("weekly-kpi-triage", mission_version=1)

    assert stats.shadow_runs_passed == 10
    assert stats.critical_violations == 0
    assert stats.verifier_avg_score == 0.90
    assert stats.rollback_rehearsal_passed is True
    assert latest is not None
    assert latest.approved_by == ("owner-park", "owner-cho")
    assert store.is_certified("weekly-kpi-triage", "autopilot", mission_version=1) is True
