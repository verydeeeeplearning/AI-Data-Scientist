from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from ds_agent.application.dtos.delivery import (
    DeliveryLogQueryResult,
    DeliveryLogSummary,
    DispatchLogRecord,
)
from ds_agent.domain.entities.assumption_log import AssumptionLog
from ds_agent.domain.entities.delivery_pack import DeliveryChannel, DeliveryPack
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.review_verdict import ConfidenceBand, LayerResult, ReviewVerdict
from ds_agent.domain.entities.task_contract import TaskContract, TaskContractStatus
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.skills.mission_pack_loader import MissionPackLoader


def _numeric_suffix(task_id: str) -> str:
    digits = "".join(char for char in task_id if char.isdigit())
    return digits or "1"


@dataclass(frozen=True)
class FixedClock:
    now_value: datetime

    def now(self) -> datetime:
        return self.now_value


class InMemoryVerdictRepo:
    def __init__(self) -> None:
        self.saved: list[ReviewVerdict] = []

    def save(self, verdict: ReviewVerdict) -> None:
        self.saved.append(verdict)

    def get(self, verdict_id: str) -> ReviewVerdict | None:
        for verdict in self.saved:
            if verdict.verdict_id == verdict_id:
                return verdict
        return None

    def list_for_task(self, task_id: str) -> list[ReviewVerdict]:
        return [verdict for verdict in self.saved if verdict.task_id == task_id]


class StaticVerifier:
    def __init__(self, layer_result: LayerResult) -> None:
        self._layer_result = layer_result

    async def run(self, ctx: object) -> LayerResult:
        return self._layer_result


class StaticDispatchLogReader:
    def __init__(
        self,
        *,
        records: Iterable[DispatchLogRecord] = (),
        default_now: datetime,
    ) -> None:
        self._records = tuple(records)
        self._default_now = default_now

    def query(
        self,
        *,
        task_id: str,
        pack_id: str | None = None,
        artifact_ids: set[str] | None = None,
        channels: set[DeliveryChannel] | None = None,
        limit: int = 50,
    ) -> DeliveryLogQueryResult:
        filtered = [
            record
            for record in self._records
            if record.task_id == task_id
            and (pack_id is None or record.pack_id == pack_id)
            and (artifact_ids is None or record.artifact_id in artifact_ids)
            and (channels is None or record.channel in channels)
        ]
        limited = tuple(filtered[:limit])
        return DeliveryLogQueryResult(
            task_id=task_id,
            pack_id=pack_id,
            records=limited,
            summary=self._build_summary(task_id=task_id, pack_id=pack_id, records=limited),
        )

    def summarize(self, *, pack: DeliveryPack) -> DeliveryLogSummary:
        records = tuple(
            record
            for record in self._records
            if record.task_id == pack.task_id and record.pack_id == pack.pack_id
        )
        return self._build_summary(task_id=pack.task_id, pack_id=pack.pack_id, records=records)

    def _build_summary(
        self,
        *,
        task_id: str,
        pack_id: str | None,
        records: tuple[DispatchLogRecord, ...],
    ) -> DeliveryLogSummary:
        counts = {
            "sent": 0,
            "blocked": 0,
            "duplicate": 0,
            "failed": 0,
            "dry_run": 0,
        }
        last_attempt = self._default_now
        if records:
            last_attempt = max(record.recorded_at for record in records)
        for record in records:
            counts[record.status] += 1
        return DeliveryLogSummary(
            task_id=task_id,
            pack_id=pack_id or "unknown-pack",
            pack_status="rendered",
            artifact_count=len({record.artifact_id for record in records}),
            rendered_count=len({record.artifact_id for record in records}),
            sent=counts["sent"],
            blocked=counts["blocked"],
            duplicate=counts["duplicate"],
            failed=counts["failed"],
            dry_run=counts["dry_run"],
            last_attempt=last_attempt,
        )


@pytest.fixture
def fixed_now() -> datetime:
    return datetime(2026, 4, 21, 9, 0, tzinfo=UTC)


@pytest.fixture
def fixed_clock(fixed_now: datetime) -> FixedClock:
    return FixedClock(now_value=fixed_now)


@pytest.fixture
def mission_loader() -> MissionPackLoader:
    return MissionPackLoader()


@pytest.fixture
def verdict_repo() -> InMemoryVerdictRepo:
    return InMemoryVerdictRepo()


@pytest.fixture
def static_verifier_factory():
    def _make(layer_result: LayerResult) -> StaticVerifier:
        return StaticVerifier(layer_result)

    return _make


@pytest.fixture
def dispatch_log_reader_factory(fixed_now: datetime):
    def _make(*, records: Iterable[DispatchLogRecord] = ()) -> StaticDispatchLogReader:
        return StaticDispatchLogReader(records=records, default_now=fixed_now)

    return _make


@pytest.fixture
def make_task_contract(fixed_now: datetime):
    def _make(
        *,
        task_id: str = "TC-2026-001",
        mission: str | None = None,
        status: TaskContractStatus = TaskContractStatus.DRAFT,
        required_deliverables: list[dict[str, str]] | None = None,
        definition_of_done: dict[str, object] | None = None,
    ) -> TaskContract:
        return TaskContract(
            task_id=task_id,
            session_id="session-1",
            type="churn_analysis",
            status=status,
            business_goal="Reduce churn",
            mission=mission,
            required_deliverables=required_deliverables
            or [{"type": "exec_brief", "audience": "executive", "format": "pptx"}],
            definition_of_done=definition_of_done,
            goal_brief_id=f"GB-{_numeric_suffix(task_id)}",
            assumption_log_id=f"AL-{_numeric_suffix(task_id)}",
            created_at=fixed_now,
            updated_at=fixed_now,
        )

    return _make


@pytest.fixture
def make_contract_bundle(fixed_now: datetime, make_task_contract):
    def _make(
        *,
        task_id: str = "TC-2026-001",
        mission: str | None = None,
        status: TaskContractStatus = TaskContractStatus.DRAFT,
        required_deliverables: list[dict[str, str]] | None = None,
        definition_of_done: dict[str, object] | None = None,
    ) -> TaskContractBundle:
        contract = make_task_contract(
            task_id=task_id,
            mission=mission,
            status=status,
            required_deliverables=required_deliverables,
            definition_of_done=definition_of_done,
        )
        bundle = TaskContractBundle(
            contract=contract,
            goal_brief=GoalBrief(
                brief_id=f"GB-{_numeric_suffix(task_id)}",
                task_id=task_id,
                business_question="Why is churn rising?",
                ds_problem_statement="Binary classification",
                comparison_baseline="previous quarter",
                decision_to_make="choose top interventions",
                expected_effort="M",
                created_at=fixed_now,
                updated_at=fixed_now,
            ),
            assumption_log=AssumptionLog(
                log_id=f"AL-{_numeric_suffix(task_id)}",
                task_id=task_id,
            ),
        )
        return bundle.sync_references()

    return _make


@pytest.fixture
def make_review_verdict(fixed_now: datetime):
    def _make(
        *,
        task_id: str = "TC-2026-001",
        verdict_id: str = "RV-2026001",
        category: str = "orchestrator",
        result: str = "pass",
        summary: str = "Verifier passed",
        confidence_score: float | None = 0.72,
        created_at: datetime | None = None,
        reviewer: str = "verifier",
        run_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ReviewVerdict:
        return ReviewVerdict(
            verdict_id=verdict_id,
            task_id=task_id,
            category=category,  # type: ignore[arg-type]
            result=result,  # type: ignore[arg-type]
            reviewer=reviewer,
            summary=summary,
            created_at=created_at or fixed_now,
            run_id=run_id,
            metadata=dict(metadata or {}),
            confidence=(
                ConfidenceBand(score=confidence_score) if confidence_score is not None else None
            ),
        )

    return _make


@pytest.fixture
def make_delivery_pack(fixed_now: datetime):
    def _make(
        *,
        task_id: str = "TC-2026-001",
        pack_id: str = "DP-2026001",
        items: list[dict[str, object]] | None = None,
    ) -> DeliveryPack:
        return DeliveryPack(
            pack_id=pack_id,
            task_id=task_id,
            generated_at=fixed_now,
            items=items
            or [
                {
                    "deliverable_type": "exec_brief",
                    "audience": "executive",
                    "format": "pptx",
                    "artifact_path": "reports/exec.pptx",
                    "delivered": True,
                }
            ],
        )

    return _make


@pytest.fixture
def make_dispatch_record(fixed_now: datetime):
    def _make(
        *,
        task_id: str = "TC-2026-001",
        pack_id: str = "DP-2026001",
        artifact_id: str = "artifact-1",
        channel: DeliveryChannel = DeliveryChannel.JIRA_TICKET,
        status: str = "sent",
    ) -> DispatchLogRecord:
        return DispatchLogRecord(
            task_id=task_id,
            pack_id=pack_id,
            artifact_id=artifact_id,
            channel=channel,
            status=status,  # type: ignore[arg-type]
            idempotency_key=f"{pack_id}:{artifact_id}:{channel.value}",
            recorded_at=fixed_now,
            receipt_id=f"receipt-{artifact_id}",
            adapter_name="contract-test",
        )

    return _make
