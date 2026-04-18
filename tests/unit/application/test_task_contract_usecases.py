from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from ds_agent.application.dtos.task_contract import (
    AssumptionInputDTO,
    BuildDeliveryPackDTO,
    DeliveryPackInputDTO,
    ReviewVerdictInputDTO,
    TaskContractDraftDTO,
    TaskContractUpdateDTO,
    VerifyAssumptionDTO,
)
from ds_agent.application.services.task_contract_usecases import (
    AddAssumptionUseCase,
    BuildDeliveryPackUseCase,
    CloseTaskContractUseCase,
    CreateTaskContractUseCase,
    RecordDeliveryPackUseCase,
    RecordReviewVerdictUseCase,
    UpdateTaskContractUseCase,
    VerifyAssumptionUseCase,
)
from ds_agent.domain.entities.task_contract import TaskContractStatus
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.entities.task_contract_event import TaskContractEvent
from ds_agent.domain.errors.task_contract_errors import DoDUnmetError, VersionConflictError
from ds_agent.domain.interfaces.task_contract import TaskContractStore


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


def _draft_dto() -> TaskContractDraftDTO:
    return TaskContractDraftDTO(
        session_id="session-1",
        contract_type="churn_analysis",
        business_goal="Reduce churn by one point",
        authority="delegate",
        audience="senior_staff",
        mission="weekly-kpi-triage",
        goal_brief={
            "business_question": "What drives churn?",
            "ds_problem_statement": "Binary classification",
            "comparison_baseline": "last quarter",
            "decision_to_make": "prioritize interventions",
            "expected_effort": "M",
        },
        required_deliverables=[{"type": "exec_brief", "audience": "executive", "format": "pptx"}],
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
        ReviewVerdictInputDTO(
            task_id="TC-2026-001",
            category="statistical",
            result="pass",
            reviewer="agent",
            summary="Looks good",
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

    with pytest.raises(DoDUnmetError):
        CloseTaskContractUseCase(store, FixedClock(), publisher).execute(
            "TC-2026-001",
            expected_version=5,
            closing_note="done",
        )


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
        ReviewVerdictInputDTO(
            task_id="TC-2026-001",
            category="statistical",
            result="pass",
            reviewer="agent",
            summary="Looks good",
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

    result = CloseTaskContractUseCase(store, FixedClock(), publisher).execute(
        "TC-2026-001",
        expected_version=6,
        closing_note="done",
    )

    assert result["status"] == "closed"


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
        ReviewVerdictInputDTO(
            task_id="TC-2026-001",
            category="orchestrator",
            result="warn",
            reviewer="verifier",
            summary="Low confidence",
            confidence={"score": 0.32},
        )
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
