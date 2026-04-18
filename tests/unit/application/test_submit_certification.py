from datetime import UTC, datetime

from ds_agent.application.services.certification_usecases import (
    GetCertificationStatusUseCase,
    SubmitCertificationInput,
    SubmitCertificationUseCase,
)
from ds_agent.domain.entities.certification import (
    AutonomyRunStat,
    CertificationRecord,
    CertificationStats,
)
from ds_agent.domain.entities.mission_pack import MissionPack


def _mission_pack() -> MissionPack:
    return MissionPack.model_validate(
        {
            "name": "weekly-kpi-triage",
            "version": 1,
            "summary": "Weekly KPI anomaly triage.",
            "authority_default": "delegate",
            "audience_default": "senior_staff",
            "boundary": {
                "allowed_data_domains": ["growth", "sales"],
                "required_semantic_metrics": ["dau"],
                "allowed_action_classes": ["artifact_draft", "jira_create"],
            },
            "required_checks": ["schema_drift"],
            "required_artifacts": ["exec_brief"],
            "success_criteria": ["issue_classified"],
            "certification": {
                "current_level": "delegate",
                "next_target": "autopilot",
                "autopilot_requirements": {
                    "shadow_runs_passed": 10,
                    "critical_violations": 0,
                    "verifier_avg_score": 0.85,
                    "rollback_rehearsal": "passed",
                    "owner_approvals": 2,
                },
            },
        }
    )


class StubMissionLoader:
    def load(self, name: str) -> MissionPack:
        assert name == "weekly-kpi-triage"
        return _mission_pack()


class StubCertificationStore:
    def __init__(
        self,
        stats: CertificationStats,
        latest: CertificationRecord | None = None,
    ) -> None:
        self.stats = stats
        self.latest = latest
        self.saved: list[CertificationRecord] = []

    def save_certification(self, record: CertificationRecord) -> None:
        self.saved.append(record)
        self.latest = record

    def latest_certification(
        self,
        mission_name: str,
        *,
        mission_version: int | None = None,
    ) -> CertificationRecord | None:
        return self.latest

    def list_certifications(
        self,
        mission_name: str,
        *,
        mission_version: int | None = None,
        limit: int = 20,
    ) -> list[CertificationRecord]:
        return list(self.saved)[-limit:]

    def is_certified(
        self,
        mission_name: str,
        level: object,
        *,
        mission_version: int | None = None,
    ) -> bool:
        level_value = getattr(level, "value", level)
        return self.latest is not None and self.latest.level.value == level_value

    def record_run_stat(self, stat: AutonomyRunStat) -> None:
        raise AssertionError("not used")

    def stats_for(
        self,
        mission_name: str,
        *,
        mission_version: int | None = None,
    ) -> CertificationStats:
        return self.stats


def test_submit_certification_returns_pending_when_gaps_exist() -> None:
    store = StubCertificationStore(
        CertificationStats(
            shadow_runs_passed=8,
            critical_violations=1,
            verifier_avg_score=0.81,
            rollback_rehearsal_passed=False,
        )
    )

    result = SubmitCertificationUseCase(StubMissionLoader(), store).execute(
        SubmitCertificationInput(
            mission_name="weekly-kpi-triage",
            target_level="autopilot",
        )
    )

    assert result.status == "pending"
    assert result.gaps
    assert not store.saved


def test_submit_certification_waits_for_required_owner_approvals() -> None:
    store = StubCertificationStore(
        CertificationStats(
            shadow_runs_passed=10,
            critical_violations=0,
            verifier_avg_score=0.90,
            rollback_rehearsal_passed=True,
        )
    )

    result = SubmitCertificationUseCase(StubMissionLoader(), store).execute(
        SubmitCertificationInput(
            mission_name="weekly-kpi-triage",
            target_level="autopilot",
            approved_by=("owner-park",),
        )
    )

    assert result.status == "awaiting_approval"
    assert result.required_approvers == 2
    assert not store.saved


def test_submit_certification_persists_record_when_requirements_are_met() -> None:
    store = StubCertificationStore(
        CertificationStats(
            shadow_runs_passed=12,
            critical_violations=0,
            verifier_avg_score=0.91,
            rollback_rehearsal_passed=True,
        )
    )
    use_case = SubmitCertificationUseCase(
        StubMissionLoader(),
        store,
        clock=lambda: datetime(2026, 4, 16, tzinfo=UTC),
    )

    result = use_case.execute(
        SubmitCertificationInput(
            mission_name="weekly-kpi-triage",
            target_level="autopilot",
            approved_by=("owner-park", "owner-cho"),
            evidence_ref="certification/ev-2026-04-16.md",
        )
    )

    assert result.status == "certified"
    assert result.certification is not None
    assert result.certification.level.value == "autopilot"
    assert result.certification.approved_by == ("owner-park", "owner-cho")
    assert store.saved


def test_status_use_case_combines_yaml_level_and_store_level() -> None:
    store = StubCertificationStore(
        CertificationStats(
            shadow_runs_passed=10,
            critical_violations=0,
            verifier_avg_score=0.88,
            rollback_rehearsal_passed=True,
        ),
        latest=CertificationRecord(
            mission_name="weekly-kpi-triage",
            mission_version=1,
            level="autopilot",
            transition_from="delegate",
            approved_by=("owner-park", "owner-cho"),
            approved_at=datetime(2026, 4, 16, tzinfo=UTC),
        ),
    )

    result = GetCertificationStatusUseCase(StubMissionLoader(), store).execute(
        "weekly-kpi-triage"
    )

    assert result.current_level is not None
    assert result.current_level.value == "delegate"
    assert result.effective_level is not None
    assert result.effective_level.value == "autopilot"
    assert result.certified_for_next_target is True
