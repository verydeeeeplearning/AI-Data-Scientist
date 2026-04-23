from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ds_agent.application.dtos.delivery import (
    DeliveryLogQueryResult,
    DeliveryLogSummary,
    DispatchLogRecord,
)
from ds_agent.application.dtos.task_contract import (
    AssumptionInputDTO,
    BuildDeliveryPackDTO,
    DeliveryPackInputDTO,
    ReviewVerdictInputDTO,
    TaskContractDraftDTO,
    TaskContractUpdateDTO,
    VerifyAssumptionDTO,
)
from ds_agent.application.services.mission_required_artifacts import (
    MissionRequiredArtifactResolver,
)
from ds_agent.application.services.mission_required_delivery_channels import (
    MissionRequiredDeliveryChannelResolver,
)
from ds_agent.application.services.task_contract_usecases import (
    AddAssumptionUseCase,
    BuildDeliveryPackUseCase,
    CloseTaskContractUseCase,
    CreateTaskContractUseCase,
    GetTaskContractUseCase,
    RecordDeliveryPackUseCase,
    RecordReviewVerdictUseCase,
    UpdateTaskContractUseCase,
    VerifyAssumptionUseCase,
)
from ds_agent.domain.entities.delivery_pack import DeliveryChannel, DeliveryPack
from ds_agent.domain.entities.task_contract import TaskContractStatus
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.entities.task_contract_event import TaskContractEvent
from ds_agent.domain.errors.task_contract_errors import (
    DoDUnmetError,
    InvalidTransitionError,
    VersionConflictError,
)
from ds_agent.domain.interfaces.task_contract import TaskContractStore
from ds_agent.skills.mission_pack_loader import MissionPackLoader


class InMemoryTaskContractStore(TaskContractStore):
    def __init__(self) -> None:
        self.bundles: dict[str, TaskContractBundle] = {}
        self.events: list[TaskContractEvent] = []

    def create_bundle(
        self,
        bundle: TaskContractBundle,
        *,
        events: Sequence[TaskContractEvent] = (),
    ) -> None:
        self.bundles[bundle.contract.task_id] = bundle.model_copy(deep=True)
        self.events.extend(events)

    def get_bundle(self, task_id: str) -> TaskContractBundle | None:
        bundle = self.bundles.get(task_id)
        return bundle.model_copy(deep=True) if bundle else None

    def get_active_bundle(self, session_id: str) -> TaskContractBundle | None:
        for bundle in self.bundles.values():
            if bundle.contract.session_id == session_id and not bundle.contract.is_terminal:
                return bundle.model_copy(deep=True)
        return None

    def list_contracts(
        self,
        session_id: str | None = None,
        *,
        statuses: Sequence[TaskContractStatus] | None = None,
        limit: int = 20,
    ) -> list:
        results = [
            bundle.contract.model_copy(deep=True)
            for bundle in self.bundles.values()
            if (session_id is None or bundle.contract.session_id == session_id)
            and (not statuses or bundle.contract.status in set(statuses))
        ]
        results.sort(key=lambda contract: contract.updated_at, reverse=True)
        return results[:limit]

    def save_bundle(
        self,
        bundle: TaskContractBundle,
        *,
        expected_version: int,
        events: Sequence[TaskContractEvent] = (),
    ) -> None:
        current = self.bundles.get(bundle.contract.task_id)
        if current is None:
            raise VersionConflictError("missing contract")
        if current.contract.version != expected_version:
            raise VersionConflictError("stale version")
        self.bundles[bundle.contract.task_id] = bundle.model_copy(deep=True)
        self.events.extend(events)


@dataclass
class FixedClock:
    now_value: datetime = datetime(2026, 4, 15, tzinfo=UTC)

    def now(self) -> datetime:
        return self.now_value


@dataclass
class FixedIds:
    index: int = 0

    def new_task_id(self, now: datetime) -> str:
        return f"TC-{now.year}-001"

    def new_artifact_id(self, prefix: str) -> str:
        self.index += 1
        return f"{prefix}-{self.index}"


@dataclass
class Publisher:
    events: list[TaskContractEvent] = field(default_factory=list)

    def publish(self, event: TaskContractEvent) -> None:
        self.events.append(event)


@dataclass
class FailureSignalRecorder:
    calls: list[dict[str, object]] = field(default_factory=list)

    def record_transition_failure(
        self,
        *,
        task_id: str,
        session_id: str | None,
        run_id: str | None,
        transition_to: str | None,
        error_code: str,
        message: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.calls.append(
            {
                "task_id": task_id,
                "session_id": session_id,
                "run_id": run_id,
                "transition_to": transition_to,
                "error_code": error_code,
                "message": message,
                "metadata": dict(metadata or {}),
            }
        )


class StubDeliveryDispatchLogReader:
    def __init__(self, records: list[DispatchLogRecord]) -> None:
        self._records = tuple(records)

    def query(
        self,
        *,
        task_id: str,
        pack_id: str | None = None,
        artifact_ids: set[str] | None = None,
        channels: set[DeliveryChannel] | None = None,
        limit: int = 50,
    ) -> DeliveryLogQueryResult:
        channel_values = {channel.value for channel in channels} if channels is not None else None
        filtered = [
            record
            for record in self._records
            if record.task_id == task_id
            and (pack_id is None or record.pack_id == pack_id)
            and (artifact_ids is None or record.artifact_id in artifact_ids)
            and (channel_values is None or record.channel.value in channel_values)
        ]
        return DeliveryLogQueryResult(
            task_id=task_id,
            pack_id=pack_id,
            log_path=Path("delivery_dispatch_log.jsonl"),
            records=tuple(filtered[:limit]),
        )

    def summarize(self, *, pack: DeliveryPack) -> DeliveryLogSummary:
        return DeliveryLogSummary(
            task_id=pack.task_id,
            pack_id=pack.pack_id,
            pack_status=pack.status.value,
        )


def _draft_dto(
    *,
    mission: str = "weekly-kpi-triage",
    required_deliverables: list[dict[str, str]] | None = None,
) -> TaskContractDraftDTO:
    return TaskContractDraftDTO(
        session_id="session-1",
        contract_type="churn_analysis",
        business_goal="Reduce churn by one point",
        authority="delegate",
        audience="senior_staff",
        mission=mission,
        goal_brief={
            "business_question": "What drives churn?",
            "ds_problem_statement": "Binary classification",
            "comparison_baseline": "last quarter",
            "decision_to_make": "prioritize interventions",
            "expected_effort": "M",
        },
        required_deliverables=required_deliverables
        or [{"type": "exec_brief", "audience": "executive", "format": "pptx"}],
    )


def _auto_review_verdict_input(
    task_id: str,
    *,
    summary: str = "Looks good",
    result: str = "pass",
    metadata: dict[str, object] | None = None,
) -> ReviewVerdictInputDTO:
    base_metadata: dict[str, object] = {
        "source": "auto_verifier",
        "auto_verifier_mode": "shadow",
    }
    if metadata:
        base_metadata.update(metadata)
    return ReviewVerdictInputDTO(
        task_id=task_id,
        category="orchestrator",
        result=result,  # type: ignore[arg-type]
        reviewer="verifier_orchestrator",
        summary=summary,
        run_id="run-1",
        metadata=base_metadata,
    )


def _mission_required_artifact_metadata(
    *,
    mission_name: str,
    required_artifacts: tuple[str, ...],
    mapped_required_artifacts: dict[str, tuple[str, ...]],
    unmapped_required_artifacts: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "mission_name": mission_name,
        "mission_pack_loaded": True,
        "mission_required_artifacts": list(required_artifacts),
        "mission_required_artifact_map": {
            required_artifact: list(mapped_artifacts)
            for required_artifact, mapped_artifacts in mapped_required_artifacts.items()
        },
        "mission_unmapped_required_artifacts": list(unmapped_required_artifacts),
    }


def _mission_required_check_metadata(
    *,
    mission_name: str,
    required_checks: tuple[str, ...],
    mapped_required_checks: dict[str, tuple[str, ...]],
    required_check_results: dict[str, str],
    unmapped_required_checks: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "mission_name": mission_name,
        "mission_pack_loaded": True,
        "mission_required_checks": list(required_checks),
        "mission_required_check_map": {
            required_check: list(mapped_check_ids)
            for required_check, mapped_check_ids in mapped_required_checks.items()
        },
        "mission_unmapped_required_checks": list(unmapped_required_checks),
        "mission_required_check_results": dict(required_check_results),
        "mission_required_check_failures": [
            required_check
            for required_check, status in required_check_results.items()
            if status in {"fail", "error", "missing"}
        ],
    }


def _mission_artifact_resolver() -> MissionRequiredArtifactResolver:
    return MissionRequiredArtifactResolver(MissionPackLoader())


def _mission_delivery_channel_resolver(
    records: list[DispatchLogRecord] | None = None,
) -> MissionRequiredDeliveryChannelResolver:
    return MissionRequiredDeliveryChannelResolver(
        MissionPackLoader(),
        StubDeliveryDispatchLogReader(records or []),
    )


def _dispatch_record(*, pack_id: str, status: str = "sent") -> DispatchLogRecord:
    return DispatchLogRecord(
        task_id="TC-2026-001",
        pack_id=pack_id,
        artifact_id="ART-1",
        channel=DeliveryChannel.JIRA_TICKET,
        status=status,
        idempotency_key=f"key-{status}",
        recorded_at=datetime(2026, 4, 21, tzinfo=UTC),
    )


def test_create_task_contract_generates_goal_brief_and_event() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    result = CreateTaskContractUseCase(
        store,
        FixedClock(),
        FixedIds(),
        publisher,
    ).execute(_draft_dto())

    assert result["task_id"] == "TC-2026-001"
    bundle = store.get_bundle("TC-2026-001")
    assert bundle is not None
    assert bundle.goal_brief is not None
    assert bundle.assumption_log is not None
    assert bundle.contract.authority is not None
    assert bundle.contract.authority.value == "delegate"
    assert bundle.contract.audience is not None
    assert bundle.contract.audience.value == "senior_staff"
    assert bundle.contract.mission == "weekly-kpi-triage"
    assert publisher.events[0].event_type == "task_contract.created"


def test_update_task_contract_detects_version_conflict() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    create = CreateTaskContractUseCase(store, FixedClock(), FixedIds(), publisher)
    create.execute(_draft_dto())

    with pytest.raises(VersionConflictError):
        UpdateTaskContractUseCase(store, FixedClock(), publisher).execute(
            TaskContractUpdateDTO(
                task_id="TC-2026-001",
                expected_version=99,
                patch={"decision_owner": "pm@corp"},
            )
        )


def test_add_assumption_marks_high_risk_for_user_confirmation() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(_draft_dto())

    result = AddAssumptionUseCase(store, FixedClock(), ids, publisher).execute(
        AssumptionInputDTO(
            task_id="TC-2026-001",
            statement="Churn = 30 days inactive",
            rationale="Team convention",
            risk_level="high",
        )
    )

    assert result["requires_user_confirmation"] is True


def test_verify_assumption_marks_entry_verified_and_bumps_version() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(_draft_dto())

    added = AddAssumptionUseCase(store, FixedClock(), ids, publisher).execute(
        AssumptionInputDTO(
            task_id="TC-2026-001",
            statement="Churn = 30 days inactive",
            rationale="Team convention",
            risk_level="medium",
        )
    )

    result = VerifyAssumptionUseCase(store, FixedClock(), publisher).execute(
        VerifyAssumptionDTO(
            task_id="TC-2026-001",
            entry_id=added["entry_id"],
            expected_version=2,
            verification_note="Confirmed against the retention dashboard definition.",
        )
    )

    bundle = store.get_bundle("TC-2026-001")
    assert bundle is not None
    assert result["verified"] is True
    assert result["new_version"] == 3
    assert bundle.assumption_log is not None
    assert bundle.assumption_log.entries[0].verified is True
    assert (
        bundle.assumption_log.entries[0].verification_note
        == "Confirmed against the retention dashboard definition."
    )


def test_record_review_verdict_preserves_supplied_verdict_id() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(_draft_dto())

    result = RecordReviewVerdictUseCase(store, FixedClock(), ids, publisher).execute(
        ReviewVerdictInputDTO(
            task_id="TC-2026-001",
            verdict_id="RV-999",
            category="orchestrator",
            result="warn",
            reviewer="verifier",
            summary="Needs follow-up",
        )
    )

    bundle = store.get_bundle("TC-2026-001")
    assert bundle is not None
    assert result["verdict_id"] == "RV-999"
    assert bundle.review_verdicts[0].verdict_id == "RV-999"


def test_get_task_contract_includes_mission_artifact_summary() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(
        _draft_dto(
            mission="data_analysis",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            ],
        )
    )

    view = GetTaskContractUseCase(
        store,
        FixedClock(),
        publisher,
        _mission_artifact_resolver(),
    ).execute("TC-2026-001", include=["goal_brief"])

    assert "Mission artifacts [data_analysis]: required=exec_brief, ds_appendix" in view.dod_summary
    assert "Mission artifacts gate: contract_missing=ds_appendix" in view.dod_summary


def test_get_task_contract_includes_mission_delivery_channel_summary() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(
        _draft_dto(
            mission="weekly-kpi-triage",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            ],
        )
    )
    RecordDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        DeliveryPackInputDTO(
            task_id="TC-2026-001",
            items=[
                {
                    "deliverable_type": "exec_brief",
                    "audience": "executive",
                    "format": "pptx",
                    "artifact_path": "reports/exec.pptx",
                    "delivered": True,
                },
                {
                    "deliverable_type": "ds_appendix",
                    "audience": "ds_peer",
                    "format": "markdown",
                    "artifact_path": "reports/appendix.md",
                    "delivered": True,
                },
            ],
        )
    )

    view = GetTaskContractUseCase(
        store,
        FixedClock(),
        publisher,
        _mission_artifact_resolver(),
        _mission_delivery_channel_resolver(),
    ).execute("TC-2026-001", include=["delivery_pack"])

    assert "Mission delivery channels [weekly-kpi-triage]: required=jira_ticket" in view.dod_summary
    assert "Mission delivery channels gate: delivery_missing=jira_ticket" in view.dod_summary


def test_build_delivery_pack_derives_typed_artifacts_from_required_deliverables() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    create = CreateTaskContractUseCase(store, FixedClock(), ids, publisher)
    create.execute(
        TaskContractDraftDTO(
            session_id="session-1",
            contract_type="churn_analysis",
            business_goal="Reduce churn by one point",
            goal_brief={
                "business_question": "What drives churn?",
                "ds_problem_statement": "Binary classification",
                "comparison_baseline": "last quarter",
                "decision_to_make": "prioritize interventions",
                "expected_effort": "M",
            },
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "pm_action_memo", "audience": "pm", "format": "markdown"},
                {"type": "ds_experiment_note", "audience": "ds_peer", "format": "ipynb"},
            ],
        )
    )

    result = BuildDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        BuildDeliveryPackDTO(
            task_id="TC-2026-001",
            source_analysis_id="FA-1",
            signed_by="ds-agent@test",
            global_context={"project": "churn_q2"},
        )
    )

    bundle = store.get_bundle("TC-2026-001")
    assert bundle is not None
    assert bundle.delivery_pack is not None
    assert result["artifacts"] == 3
    assert result["status"] == "draft"
    assert bundle.delivery_pack.source_analysis_id == "FA-1"
    assert bundle.delivery_pack.signed_by == "ds-agent@test"
    assert bundle.delivery_pack.global_context["project"] == "churn_q2"
    assert {artifact.audience.value for artifact in bundle.delivery_pack.artifacts} == {
        "executive",
        "pm",
        "ds_peer",
    }
    assert all(item.delivered is False for item in bundle.delivery_pack.items)
    assert publisher.events[-1].event_type == "task_contract.delivery_pack_built"


def test_build_delivery_pack_adds_missing_mission_delivery_channel_to_primary_artifact() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(
        _draft_dto(
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            ]
        )
    )

    result = BuildDeliveryPackUseCase(
        store,
        FixedClock(),
        ids,
        publisher,
        _mission_delivery_channel_resolver(),
    ).execute(BuildDeliveryPackDTO(task_id="TC-2026-001", audiences=["executive"]))

    bundle = store.get_bundle("TC-2026-001")
    assert bundle is not None
    assert bundle.delivery_pack is not None
    assert result["audiences"] == ["executive"]
    artifact = bundle.delivery_pack.artifacts[0]
    assert artifact.audience.value == "executive"
    assert [channel.value for channel in artifact.delivery_channel] == [
        "email",
        "slack_dm",
        "jira_ticket",
    ]
    assert bundle.delivery_pack.global_context["mission_required_delivery_channels"] == (
        "jira_ticket"
    )


def test_build_delivery_pack_prefers_ds_appendix_for_mission_jira_channel_when_available() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(
        _draft_dto(
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            ]
        )
    )

    BuildDeliveryPackUseCase(
        store,
        FixedClock(),
        ids,
        publisher,
        _mission_delivery_channel_resolver(),
    ).execute(BuildDeliveryPackDTO(task_id="TC-2026-001"))

    bundle = store.get_bundle("TC-2026-001")
    assert bundle is not None
    assert bundle.delivery_pack is not None

    channels_by_audience = {
        artifact.audience.value: [channel.value for channel in artifact.delivery_channel]
        for artifact in bundle.delivery_pack.artifacts
    }
    assert channels_by_audience["executive"] == ["email", "slack_dm"]
    assert channels_by_audience["ds_peer"] == ["git_pr", "jira_ticket"]


def test_build_delivery_pack_can_filter_audiences() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(
        TaskContractDraftDTO(
            session_id="session-1",
            contract_type="churn_analysis",
            business_goal="Reduce churn by one point",
            goal_brief={
                "business_question": "What drives churn?",
                "ds_problem_statement": "Binary classification",
                "comparison_baseline": "last quarter",
                "decision_to_make": "prioritize interventions",
                "expected_effort": "M",
            },
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "audit_trail", "audience": "auditor", "format": "pdf"},
            ],
        )
    )

    result = BuildDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        BuildDeliveryPackDTO(task_id="TC-2026-001", audiences=["auditor"])
    )

    bundle = store.get_bundle("TC-2026-001")
    assert bundle is not None
    assert bundle.delivery_pack is not None
    assert result["artifacts"] == 1
    assert result["audiences"] == ["auditor"]
    assert bundle.delivery_pack.artifact_for("auditor") is not None
    assert bundle.delivery_pack.artifact_for("executive") is None


def test_close_task_contract_requires_review_and_delivery() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(_draft_dto())
    updater = UpdateTaskContractUseCase(store, FixedClock(), publisher)
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=1,
            patch={},
            transition_to=TaskContractStatus.AGREED,
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=2,
            patch={},
            transition_to=TaskContractStatus.IN_PROGRESS,
        )
    )
    RecordReviewVerdictUseCase(store, FixedClock(), ids, publisher).execute(
        _auto_review_verdict_input("TC-2026-001")
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=4,
            patch={},
            transition_to=TaskContractStatus.REVIEW,
        )
    )

    with pytest.raises(DoDUnmetError):
        CloseTaskContractUseCase(store, FixedClock(), publisher).execute(
            "TC-2026-001",
            expected_version=5,
            closing_note="done",
        )


def test_update_task_contract_rejects_stale_auto_verifier_run_context_for_review() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(_draft_dto())
    updater = UpdateTaskContractUseCase(store, FixedClock(), publisher)
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=1,
            patch={},
            transition_to=TaskContractStatus.AGREED,
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=2,
            patch={},
            transition_to=TaskContractStatus.IN_PROGRESS,
        )
    )
    RecordReviewVerdictUseCase(store, FixedClock(), ids, publisher).execute(
        _auto_review_verdict_input("TC-2026-001")
    )

    with pytest.raises(InvalidTransitionError, match="active run") as excinfo:
        updater.execute(
            TaskContractUpdateDTO(
                task_id="TC-2026-001",
                expected_version=4,
                patch={},
                transition_to=TaskContractStatus.REVIEW,
                run_id="run-2",
            )
        )

    assert excinfo.value.metadata["failure"] == "stale_review_verdict"
    assert excinfo.value.metadata["expected_run_id"] == "run-2"
    assert excinfo.value.metadata["latest_verdict_run_id"] == "run-1"


def test_update_task_contract_records_review_gate_failure_signal_on_transition_error() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    recorder = FailureSignalRecorder()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(_draft_dto())
    updater = UpdateTaskContractUseCase(
        store,
        FixedClock(),
        publisher,
        failure_signal_recorder=recorder,
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=1,
            patch={},
            transition_to=TaskContractStatus.AGREED,
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=2,
            patch={},
            transition_to=TaskContractStatus.IN_PROGRESS,
        )
    )
    RecordReviewVerdictUseCase(store, FixedClock(), ids, publisher).execute(
        _auto_review_verdict_input("TC-2026-001")
    )

    with pytest.raises(InvalidTransitionError, match="active run"):
        updater.execute(
            TaskContractUpdateDTO(
                task_id="TC-2026-001",
                expected_version=4,
                patch={},
                transition_to=TaskContractStatus.REVIEW,
                run_id="run-2",
            )
        )

    assert recorder.calls == [
        {
            "task_id": "TC-2026-001",
            "session_id": "session-1",
            "run_id": "run-2",
            "transition_to": "review",
            "error_code": "INVALID_TRANSITION",
            "message": (
                "Latest auto verifier verdict must match the active run before moving to review"
            ),
            "metadata": {
                "kind": "verifier_review_gate",
                "transition_target": "review",
                "failure": "stale_review_verdict",
                "review_verdict_count": 1,
                "orchestrator_verdict_count": 1,
                "expected_run_id": "run-2",
                "latest_verdict_id": "RV-1",
                "latest_verdict_category": "orchestrator",
                "latest_verdict_reviewer": "verifier_orchestrator",
                "latest_verdict_run_id": "run-1",
                "latest_verdict_source": "auto_verifier",
            },
        }
    ]


def test_close_task_contract_succeeds_after_review_and_delivery() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(_draft_dto())
    updater = UpdateTaskContractUseCase(store, FixedClock(), publisher)
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=1,
            patch={},
            transition_to=TaskContractStatus.AGREED,
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=2,
            patch={},
            transition_to=TaskContractStatus.IN_PROGRESS,
        )
    )
    RecordReviewVerdictUseCase(store, FixedClock(), ids, publisher).execute(
        _auto_review_verdict_input("TC-2026-001")
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=4,
            patch={},
            transition_to=TaskContractStatus.REVIEW,
        )
    )
    RecordDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        DeliveryPackInputDTO(
            task_id="TC-2026-001",
            items=[
                {
                    "deliverable_type": "exec_brief",
                    "audience": "executive",
                    "format": "pptx",
                    "artifact_path": "reports/exec.pptx",
                    "delivered": True,
                }
            ],
        )
    )

    result = CloseTaskContractUseCase(store, FixedClock(), publisher).execute(
        "TC-2026-001",
        expected_version=6,
        closing_note="done",
    )

    assert result["status"] == "closed"


def test_close_task_contract_rejects_missing_mission_required_delivered_artifact() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(
        _draft_dto(
            mission="data_analysis",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            ],
        )
    )
    resolver = _mission_artifact_resolver()
    updater = UpdateTaskContractUseCase(store, FixedClock(), publisher, resolver)
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=1,
            patch={},
            transition_to=TaskContractStatus.AGREED,
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=2,
            patch={},
            transition_to=TaskContractStatus.IN_PROGRESS,
        )
    )
    RecordReviewVerdictUseCase(store, FixedClock(), ids, publisher).execute(
        _auto_review_verdict_input(
            "TC-2026-001",
            summary="Mission artifact coverage is complete",
            metadata=_mission_required_artifact_metadata(
                mission_name="data_analysis",
                required_artifacts=("exec_brief", "ds_appendix"),
                mapped_required_artifacts={
                    "exec_brief": ("exec_brief",),
                    "ds_appendix": ("ds_appendix",),
                },
            ),
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=4,
            patch={},
            transition_to=TaskContractStatus.REVIEW,
        )
    )
    RecordDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        DeliveryPackInputDTO(
            task_id="TC-2026-001",
            items=[
                {
                    "deliverable_type": "exec_brief",
                    "audience": "executive",
                    "format": "pptx",
                    "artifact_path": "reports/exec.pptx",
                    "delivered": True,
                }
            ],
        )
    )

    with pytest.raises(DoDUnmetError, match=r"(?i)missing from delivered outputs: ds_appendix"):
        CloseTaskContractUseCase(store, FixedClock(), publisher, resolver).execute(
            "TC-2026-001",
            expected_version=6,
            closing_note="done",
        )


def test_update_task_contract_review_transition_rejects_failed_mission_required_checks() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(
        _draft_dto(
            mission="data_analysis",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            ],
        )
    )
    resolver = _mission_artifact_resolver()
    updater = UpdateTaskContractUseCase(store, FixedClock(), publisher, resolver)
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=1,
            patch={},
            transition_to=TaskContractStatus.AGREED,
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=2,
            patch={},
            transition_to=TaskContractStatus.IN_PROGRESS,
        )
    )
    RecordReviewVerdictUseCase(store, FixedClock(), ids, publisher).execute(
        _auto_review_verdict_input(
            "TC-2026-001",
            summary="Baseline check failed",
            metadata=_mission_required_check_metadata(
                mission_name="data_analysis",
                required_checks=(
                    "schema_drift",
                    "metric_definition_confirmed",
                    "subgroup_stability",
                    "baseline_compare",
                ),
                mapped_required_checks={
                    "schema_drift": ("schema_contract_validation",),
                    "metric_definition_confirmed": ("metric_definition_confirmed",),
                    "subgroup_stability": ("subgroup_stability",),
                    "baseline_compare": ("baseline_comparison",),
                },
                required_check_results={
                    "schema_drift": "pass",
                    "metric_definition_confirmed": "pass",
                    "subgroup_stability": "pass",
                    "baseline_compare": "fail",
                },
            ),
        )
    )

    with pytest.raises(
        InvalidTransitionError,
        match=r"(?i)must pass.*baseline_compare",
    ):
        updater.execute(
            TaskContractUpdateDTO(
                task_id="TC-2026-001",
                expected_version=4,
                patch={},
                transition_to=TaskContractStatus.REVIEW,
            )
        )


def test_close_task_contract_rejects_missing_mission_required_delivery_channel() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(
        _draft_dto(
            mission="weekly-kpi-triage",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            ],
        )
    )
    artifact_resolver = _mission_artifact_resolver()
    delivery_channel_resolver = _mission_delivery_channel_resolver()
    updater = UpdateTaskContractUseCase(store, FixedClock(), publisher, artifact_resolver)
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=1,
            patch={},
            transition_to=TaskContractStatus.AGREED,
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=2,
            patch={},
            transition_to=TaskContractStatus.IN_PROGRESS,
        )
    )
    RecordReviewVerdictUseCase(store, FixedClock(), ids, publisher).execute(
        _auto_review_verdict_input(
            "TC-2026-001",
            summary="Mission artifact coverage is complete",
            metadata=_mission_required_artifact_metadata(
                mission_name="weekly-kpi-triage",
                required_artifacts=("exec_brief", "ds_appendix"),
                mapped_required_artifacts={
                    "exec_brief": ("exec_brief",),
                    "ds_appendix": ("ds_appendix",),
                },
            ),
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=4,
            patch={},
            transition_to=TaskContractStatus.REVIEW,
        )
    )
    RecordDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        DeliveryPackInputDTO(
            task_id="TC-2026-001",
            items=[
                {
                    "deliverable_type": "exec_brief",
                    "audience": "executive",
                    "format": "pptx",
                    "artifact_path": "reports/exec.pptx",
                    "delivered": True,
                },
                {
                    "deliverable_type": "ds_appendix",
                    "audience": "ds_peer",
                    "format": "markdown",
                    "artifact_path": "reports/appendix.md",
                    "delivered": True,
                },
            ],
        )
    )

    with pytest.raises(
        DoDUnmetError,
        match=r"(?i)persisted dispatch records: jira_ticket",
    ):
        CloseTaskContractUseCase(
            store,
            FixedClock(),
            publisher,
            artifact_resolver,
            delivery_channel_resolver,
        ).execute(
            "TC-2026-001",
            expected_version=6,
            closing_note="done",
        )


def test_close_task_contract_rejects_failed_mission_required_checks() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(
        _draft_dto(
            mission="data_analysis",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            ],
        )
    )
    resolver = _mission_artifact_resolver()
    updater = UpdateTaskContractUseCase(store, FixedClock(), publisher, resolver)
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=1,
            patch={},
            transition_to=TaskContractStatus.AGREED,
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=2,
            patch={},
            transition_to=TaskContractStatus.IN_PROGRESS,
        )
    )
    RecordReviewVerdictUseCase(store, FixedClock(), ids, publisher).execute(
        _auto_review_verdict_input(
            "TC-2026-001",
            summary="Mission checks were green at review entry",
            metadata=_mission_required_check_metadata(
                mission_name="data_analysis",
                required_checks=(
                    "schema_drift",
                    "metric_definition_confirmed",
                    "subgroup_stability",
                    "baseline_compare",
                ),
                mapped_required_checks={
                    "schema_drift": ("schema_contract_validation",),
                    "metric_definition_confirmed": ("metric_definition_confirmed",),
                    "subgroup_stability": ("subgroup_stability",),
                    "baseline_compare": ("baseline_comparison",),
                },
                required_check_results={
                    "schema_drift": "pass",
                    "metric_definition_confirmed": "pass",
                    "subgroup_stability": "pass",
                    "baseline_compare": "pass",
                },
            ),
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=4,
            patch={},
            transition_to=TaskContractStatus.REVIEW,
        )
    )
    RecordReviewVerdictUseCase(store, FixedClock(), ids, publisher).execute(
        _auto_review_verdict_input(
            "TC-2026-001",
            summary="Mission required checks regressed after review entry",
            metadata=_mission_required_check_metadata(
                mission_name="data_analysis",
                required_checks=(
                    "schema_drift",
                    "metric_definition_confirmed",
                    "subgroup_stability",
                    "baseline_compare",
                ),
                mapped_required_checks={
                    "schema_drift": ("schema_contract_validation",),
                    "metric_definition_confirmed": ("metric_definition_confirmed",),
                    "subgroup_stability": ("subgroup_stability",),
                    "baseline_compare": ("baseline_comparison",),
                },
                required_check_results={
                    "schema_drift": "pass",
                    "metric_definition_confirmed": "pass",
                    "subgroup_stability": "pass",
                    "baseline_compare": "fail",
                },
            ),
        )
    )
    RecordDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        DeliveryPackInputDTO(
            task_id="TC-2026-001",
            items=[
                {
                    "deliverable_type": "exec_brief",
                    "audience": "executive",
                    "format": "pptx",
                    "artifact_path": "reports/exec.pptx",
                    "delivered": True,
                },
                {
                    "deliverable_type": "ds_appendix",
                    "audience": "ds_peer",
                    "format": "markdown",
                    "artifact_path": "reports/appendix.md",
                    "delivered": True,
                },
            ],
        )
    )

    with pytest.raises(
        DoDUnmetError,
        match=r"(?i)must pass.*baseline_compare",
    ):
        CloseTaskContractUseCase(store, FixedClock(), publisher, resolver).execute(
            "TC-2026-001",
            expected_version=7,
            closing_note="done",
        )


def test_update_task_contract_closed_transition_rejects_missing_required_delivery_channel() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(
        _draft_dto(
            mission="weekly-kpi-triage",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            ],
        )
    )
    artifact_resolver = _mission_artifact_resolver()
    delivery_channel_resolver = _mission_delivery_channel_resolver()
    updater = UpdateTaskContractUseCase(
        store,
        FixedClock(),
        publisher,
        artifact_resolver,
        delivery_channel_resolver,
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=1,
            patch={},
            transition_to=TaskContractStatus.AGREED,
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=2,
            patch={},
            transition_to=TaskContractStatus.IN_PROGRESS,
        )
    )
    RecordReviewVerdictUseCase(store, FixedClock(), ids, publisher).execute(
        _auto_review_verdict_input(
            "TC-2026-001",
            summary="Mission artifact coverage is complete",
            metadata=_mission_required_artifact_metadata(
                mission_name="weekly-kpi-triage",
                required_artifacts=("exec_brief", "ds_appendix"),
                mapped_required_artifacts={
                    "exec_brief": ("exec_brief",),
                    "ds_appendix": ("ds_appendix",),
                },
            ),
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=4,
            patch={},
            transition_to=TaskContractStatus.REVIEW,
        )
    )
    RecordDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        DeliveryPackInputDTO(
            task_id="TC-2026-001",
            items=[
                {
                    "deliverable_type": "exec_brief",
                    "audience": "executive",
                    "format": "pptx",
                    "artifact_path": "reports/exec.pptx",
                    "delivered": True,
                },
                {
                    "deliverable_type": "ds_appendix",
                    "audience": "ds_peer",
                    "format": "markdown",
                    "artifact_path": "reports/appendix.md",
                    "delivered": True,
                },
            ],
        )
    )

    with pytest.raises(
        DoDUnmetError,
        match=r"(?i)persisted dispatch records: jira_ticket",
    ):
        updater.execute(
            TaskContractUpdateDTO(
                task_id="TC-2026-001",
                expected_version=6,
                patch={},
                transition_to=TaskContractStatus.CLOSED,
            )
        )


def test_close_task_contract_accepts_required_delivery_channel_when_dispatched() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(
        _draft_dto(
            mission="weekly-kpi-triage",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            ],
        )
    )
    artifact_resolver = _mission_artifact_resolver()
    updater = UpdateTaskContractUseCase(store, FixedClock(), publisher, artifact_resolver)
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=1,
            patch={},
            transition_to=TaskContractStatus.AGREED,
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=2,
            patch={},
            transition_to=TaskContractStatus.IN_PROGRESS,
        )
    )
    RecordReviewVerdictUseCase(store, FixedClock(), ids, publisher).execute(
        _auto_review_verdict_input(
            "TC-2026-001",
            summary="Mission artifact coverage is complete",
            metadata=_mission_required_artifact_metadata(
                mission_name="weekly-kpi-triage",
                required_artifacts=("exec_brief", "ds_appendix"),
                mapped_required_artifacts={
                    "exec_brief": ("exec_brief",),
                    "ds_appendix": ("ds_appendix",),
                },
            ),
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=4,
            patch={},
            transition_to=TaskContractStatus.REVIEW,
        )
    )
    RecordDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        DeliveryPackInputDTO(
            task_id="TC-2026-001",
            items=[
                {
                    "deliverable_type": "exec_brief",
                    "audience": "executive",
                    "format": "pptx",
                    "artifact_path": "reports/exec.pptx",
                    "delivered": True,
                },
                {
                    "deliverable_type": "ds_appendix",
                    "audience": "ds_peer",
                    "format": "markdown",
                    "artifact_path": "reports/appendix.md",
                    "delivered": True,
                },
            ],
        )
    )
    bundle = store.get_bundle("TC-2026-001")
    assert bundle is not None
    assert bundle.delivery_pack is not None
    delivery_channel_resolver = _mission_delivery_channel_resolver(
        [_dispatch_record(pack_id=bundle.delivery_pack.pack_id)]
    )

    result = CloseTaskContractUseCase(
        store,
        FixedClock(),
        publisher,
        artifact_resolver,
        delivery_channel_resolver,
    ).execute(
        "TC-2026-001",
        expected_version=6,
        closing_note="done",
    )

    assert result["status"] == "closed"
    assert "Mission delivery channels gate: satisfied=jira_ticket" in result["dod_summary"]


def test_close_task_contract_enforces_verifier_confidence_threshold() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    create = CreateTaskContractUseCase(store, FixedClock(), ids, publisher)
    create.execute(_draft_dto())
    updater = UpdateTaskContractUseCase(store, FixedClock(), publisher)
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=1,
            patch={
                "definition_of_done": {
                    "criteria": ["Verifier confidence must be medium or above"],
                    "verifier": {
                        "min_confidence_grade": "medium",
                        "require_no_blocking_issues": True,
                    },
                }
            },
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=2,
            patch={},
            transition_to=TaskContractStatus.AGREED,
        )
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=3,
            patch={},
            transition_to=TaskContractStatus.IN_PROGRESS,
        )
    )
    RecordReviewVerdictUseCase(store, FixedClock(), ids, publisher).execute(
        _auto_review_verdict_input(
            "TC-2026-001",
            summary="Low confidence",
            result="warn",
        ).model_copy(update={"confidence": {"score": 0.32}})
    )
    updater.execute(
        TaskContractUpdateDTO(
            task_id="TC-2026-001",
            expected_version=5,
            patch={},
            transition_to=TaskContractStatus.REVIEW,
        )
    )
    RecordDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        DeliveryPackInputDTO(
            task_id="TC-2026-001",
            items=[
                {
                    "deliverable_type": "exec_brief",
                    "audience": "executive",
                    "format": "pptx",
                    "artifact_path": "reports/exec.pptx",
                    "delivered": True,
                }
            ],
        )
    )

    with pytest.raises(DoDUnmetError, match="Definition of Done threshold"):
        CloseTaskContractUseCase(store, FixedClock(), publisher).execute(
            "TC-2026-001",
            expected_version=7,
            closing_note="done",
        )
