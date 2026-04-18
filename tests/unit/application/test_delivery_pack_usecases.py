from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ds_agent.application.dtos.delivery import (
    DeliveryLogQueryResult,
    DeliveryLogSummary,
    DispatchDeliveryResult,
    DispatchLogRecord,
    DispatchReceipt,
    RenderedArtifact,
)
from ds_agent.application.dtos.task_contract import (
    BuildDeliveryPackDTO,
    DeliveryPackInputDTO,
    DispatchDeliveryDTO,
    ListDeliveryLogDTO,
    RenderDeliveryArtifactDTO,
    TaskContractDraftDTO,
)
from ds_agent.application.services.task_contract_usecases import (
    BuildDeliveryPackUseCase,
    CreateTaskContractUseCase,
    DispatchDeliveryUseCase,
    ListDeliveryLogUseCase,
    RecordDeliveryPackUseCase,
    RenderDeliveryArtifactUseCase,
)
from ds_agent.domain.entities.delivery_pack import (
    ArtifactFormat,
    DeliveryChannel,
    NarrativeBlocks,
)
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.entities.task_contract_event import TaskContractEvent
from ds_agent.domain.errors.task_contract_errors import VersionConflictError
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

    def list_contracts(self, session_id=None, *, statuses=None, limit: int = 20):
        del session_id, statuses, limit
        return []

    def save_bundle(
        self,
        bundle: TaskContractBundle,
        *,
        expected_version: int,
        events: Sequence[TaskContractEvent] = (),
    ) -> None:
        current = self.bundles.get(bundle.contract.task_id)
        if current is None or current.contract.version != expected_version:
            raise VersionConflictError("stale version")
        self.bundles[bundle.contract.task_id] = bundle.model_copy(deep=True)
        self.events.extend(events)


@dataclass
class FixedClock:
    now_value: datetime = datetime(2026, 4, 16, tzinfo=UTC)

    def now(self) -> datetime:
        return self.now_value


@dataclass
class FixedIds:
    index: int = 0

    def new_task_id(self, now: datetime) -> str:
        del now
        return "TC-2026-001"

    def new_artifact_id(self, prefix: str) -> str:
        self.index += 1
        return f"{prefix}-{self.index}"


@dataclass
class Publisher:
    events: list[TaskContractEvent] = field(default_factory=list)

    def publish(self, event: TaskContractEvent) -> None:
        self.events.append(event)


class FakeRenderer:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def render(
        self,
        *,
        analysis,
        output_dir: Path,
        pack,
        artifact_id: str,
        audience_profile=None,
    ) -> RenderedArtifact:
        self.calls.append(
            {
                "analysis": analysis,
                "output_dir": output_dir,
                "pack_id": pack.pack_id,
                "artifact_id": artifact_id,
                "audience_profile": audience_profile,
            }
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"{artifact_id}.md"
        target.write_text("rendered", encoding="utf-8")
        return RenderedArtifact(
            artifact_id=artifact_id,
            format=ArtifactFormat.MARKDOWN,
            output_path=target,
            narrative=NarrativeBlocks.model_validate(
                {
                    "blocks": [
                        {
                            "section": "summary",
                            "title": "Summary",
                            "body_md": "Rendered summary",
                        }
                    ],
                    "overall_tone": "actionable",
                }
            ),
            verifier_status="pass",
            verifier_report_id="vr-render",
        )


class FakeDispatcher:
    def __init__(self, result: DispatchDeliveryResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def dispatch(
        self,
        *,
        pack,
        artifact_ids=None,
        channels=None,
        dry_run: bool = False,
        approve_manual_review: bool = False,
    ) -> DispatchDeliveryResult:
        self.calls.append(
            {
                "pack_id": pack.pack_id,
                "artifact_ids": artifact_ids,
                "channels": channels,
                "dry_run": dry_run,
                "approve_manual_review": approve_manual_review,
            }
        )
        return self.result


class FakeLogReader:
    def __init__(self, result: DeliveryLogQueryResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []
        self.summary_calls: list[dict[str, object]] = []

    def query(
        self,
        *,
        task_id: str,
        pack_id: str | None = None,
        artifact_ids=None,
        channels=None,
        limit: int = 50,
    ) -> DeliveryLogQueryResult:
        self.calls.append(
            {
                "task_id": task_id,
                "pack_id": pack_id,
                "artifact_ids": artifact_ids,
                "channels": channels,
                "limit": limit,
            }
        )
        return self.result

    def summarize(self, *, pack) -> DeliveryLogSummary:
        self.summary_calls.append({"task_id": pack.task_id, "pack_id": pack.pack_id})
        return DeliveryLogSummary(
            task_id=pack.task_id,
            pack_id=pack.pack_id,
            pack_status=str(pack.status),
            artifact_count=len(pack.artifacts),
            rendered_count=sum(1 for artifact in pack.artifacts if artifact.rendered_uri),
            sent=1,
            blocked=0,
            duplicate=0,
            failed=0,
            dry_run=0,
            last_attempt=FixedClock().now(),
        )


def _create_contract(store: InMemoryTaskContractStore, ids: FixedIds, publisher: Publisher) -> None:
    CreateTaskContractUseCase(store, FixedClock(), ids, publisher).execute(
        TaskContractDraftDTO(
            session_id="session-1",
            contract_type="churn_analysis",
            business_goal="Reduce churn",
            goal_brief={
                "business_question": "Why is churn increasing?",
                "ds_problem_statement": "Predict churn_30d",
                "comparison_baseline": "Current heuristic",
                "decision_to_make": "Approve pilot",
                "expected_effort": "M",
            },
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "notebook", "audience": "ds_peer", "format": "ipynb"},
            ],
        )
    )


def test_build_delivery_pack_creates_typed_artifacts() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    _create_contract(store, ids, publisher)

    result = BuildDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        BuildDeliveryPackDTO(
            task_id="TC-2026-001",
            audiences=["executive"],
            source_analysis_id="fa-1",
            confidence=0.81,
        )
    )

    bundle = store.get_bundle("TC-2026-001")
    assert result["artifacts"] == 1
    assert result["artifact_ids"] == ["DA-3"]
    assert result["status"] == "draft"
    assert bundle is not None
    assert bundle.delivery_pack is not None
    assert bundle.delivery_pack.artifacts[0].audience.value == "executive"
    assert len(bundle.delivery_pack.items) == 1
    assert bundle.delivery_pack.items[0].artifact_path.startswith("artifact://")
    assert bundle.delivery_pack.items[0].delivered is False


def test_record_delivery_pack_accepts_typed_artifacts_without_legacy_items() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    _create_contract(store, ids, publisher)

    result = RecordDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        DeliveryPackInputDTO(
            task_id="TC-2026-001",
            artifacts=[
                {
                    "artifact_id": "art-exec",
                    "type": "exec_brief",
                    "audience": "executive",
                    "format": "pptx",
                    "content_policy": {
                        "structure": ["summary", "impact"],
                        "tone": "decisive",
                        "technical_detail": "minimal",
                        "chart_count_range": [1, 2],
                    },
                    "template_ref": "tpl/exec_brief/v3",
                    "rendered_uri": "reports/exec_brief.pptx",
                }
            ],
            status="rendered",
        )
    )

    bundle = store.get_bundle("TC-2026-001")
    assert result["artifacts"] == 1
    assert bundle is not None
    assert bundle.delivery_pack is not None
    assert len(bundle.delivery_pack.items) == 1
    assert bundle.delivery_pack.items[0].artifact_path == "reports/exec_brief.pptx"


def test_render_delivery_artifact_updates_pack_with_rendered_uri(tmp_path: Path) -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    _create_contract(store, ids, publisher)
    build = BuildDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        BuildDeliveryPackDTO(task_id="TC-2026-001", audiences=["executive"])
    )
    renderer = FakeRenderer()

    result = RenderDeliveryArtifactUseCase(
        store,
        FixedClock(),
        publisher,
        renderer,
    ).execute(
        RenderDeliveryArtifactDTO(
            task_id="TC-2026-001",
            artifact_id=build["artifact_ids"][0],
            analysis={"summary": "Top finding"},
            output_dir=str(tmp_path),
        )
    )

    bundle = store.get_bundle("TC-2026-001")
    assert result["verifier_report_id"] == "vr-render"
    assert result["pack_status"] == "rendered"
    assert Path(result["output_path"]).exists()
    assert bundle is not None
    assert bundle.delivery_pack is not None
    artifact = bundle.delivery_pack.artifacts[0]
    assert artifact.rendered_uri == result["output_path"]
    assert artifact.verifier_report_id == "vr-render"
    assert bundle.delivery_pack.items[0].artifact_path == result["output_path"]
    assert bundle.delivery_pack.items[0].delivered is True
    assert publisher.events[-1].event_type == "task_contract.delivery_artifact_rendered"


def test_dispatch_delivery_updates_pack_status_and_persists_event(tmp_path: Path) -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    _create_contract(store, ids, publisher)
    build = BuildDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        BuildDeliveryPackDTO(task_id="TC-2026-001", audiences=["executive"])
    )
    RenderDeliveryArtifactUseCase(
        store,
        FixedClock(),
        publisher,
        FakeRenderer(),
    ).execute(
        RenderDeliveryArtifactDTO(
            task_id="TC-2026-001",
            artifact_id=build["artifact_ids"][0],
            analysis={"summary": "Dispatch me"},
            output_dir=str(tmp_path),
        )
    )
    dispatcher = FakeDispatcher(
        DispatchDeliveryResult(
            task_id="TC-2026-001",
            pack_id=build["pack_id"],
            dispatch_status="dispatched",
            receipts=(
                DispatchReceipt(
                    artifact_id=build["artifact_ids"][0],
                    channel=DeliveryChannel.EMAIL,
                    status="sent",
                    idempotency_key="DP-2:DA-3:email",
                    recorded_at=FixedClock().now(),
                    receipt_id="email:1",
                    adapter_name="simulated:email",
                ),
            ),
            log_path=tmp_path / "delivery_dispatch_log.jsonl",
        )
    )

    result = DispatchDeliveryUseCase(store, FixedClock(), publisher, dispatcher).execute(
        DispatchDeliveryDTO(
            task_id="TC-2026-001",
            artifact_ids=[build["artifact_ids"][0]],
            channels=["email"],
            approve_manual_review=True,
        )
    )

    bundle = store.get_bundle("TC-2026-001")
    assert result["dispatch_status"] == "dispatched"
    assert result["sent"] == 1
    assert result["pack_status"] == "dispatched"
    assert bundle is not None
    assert bundle.delivery_pack is not None
    assert bundle.delivery_pack.status == "dispatched"
    assert bundle.contract.version == 4
    assert publisher.events[-1].event_type == "task_contract.delivery_dispatched"
    assert dispatcher.calls[0]["approve_manual_review"] is True


def test_dispatch_delivery_dry_run_keeps_pack_version_unchanged(tmp_path: Path) -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    _create_contract(store, ids, publisher)
    build = BuildDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        BuildDeliveryPackDTO(task_id="TC-2026-001", audiences=["executive"])
    )
    RenderDeliveryArtifactUseCase(
        store,
        FixedClock(),
        publisher,
        FakeRenderer(),
    ).execute(
        RenderDeliveryArtifactDTO(
            task_id="TC-2026-001",
            artifact_id=build["artifact_ids"][0],
            analysis={"summary": "Plan only"},
            output_dir=str(tmp_path),
        )
    )
    dispatcher = FakeDispatcher(
        DispatchDeliveryResult(
            task_id="TC-2026-001",
            pack_id=build["pack_id"],
            dispatch_status="dry_run",
            dry_run=True,
            receipts=(
                DispatchReceipt(
                    artifact_id=build["artifact_ids"][0],
                    channel=DeliveryChannel.EMAIL,
                    status="dry_run",
                    idempotency_key="DP-2:DA-3:email",
                    recorded_at=FixedClock().now(),
                    adapter_name="simulated:email",
                ),
            ),
            log_path=tmp_path / "delivery_dispatch_log.jsonl",
        )
    )

    result = DispatchDeliveryUseCase(store, FixedClock(), publisher, dispatcher).execute(
        DispatchDeliveryDTO(
            task_id="TC-2026-001",
            artifact_ids=[build["artifact_ids"][0]],
            dry_run=True,
        )
    )

    bundle = store.get_bundle("TC-2026-001")
    assert bundle is not None
    assert bundle.delivery_pack is not None
    assert result["dispatch_status"] == "dry_run"
    assert result["pack_status"] == "rendered"
    assert result["new_version"] == 3
    assert bundle.contract.version == 3
    assert bundle.delivery_pack.status == "rendered"


def test_list_delivery_log_returns_filtered_records() -> None:
    store = InMemoryTaskContractStore()
    publisher = Publisher()
    ids = FixedIds()
    _create_contract(store, ids, publisher)
    build = BuildDeliveryPackUseCase(store, FixedClock(), ids, publisher).execute(
        BuildDeliveryPackDTO(task_id="TC-2026-001")
    )
    pack_id = str(build["pack_id"])
    artifact_id = str(build["artifact_ids"][0])
    reader = FakeLogReader(
        DeliveryLogQueryResult(
            task_id="TC-2026-001",
            pack_id=pack_id,
            records=(
                DispatchLogRecord(
                    task_id="TC-2026-001",
                    pack_id=pack_id,
                    artifact_id=artifact_id,
                    channel=DeliveryChannel.EMAIL,
                    status="sent",
                    idempotency_key=f"{pack_id}:{artifact_id}:email",
                    recorded_at=FixedClock().now(),
                    adapter_name="simulated:email",
                    receipt_id="email:1",
                ),
            ),
        )
    )

    result = ListDeliveryLogUseCase(store, FixedClock(), publisher, reader).execute(
        ListDeliveryLogDTO(
            task_id="TC-2026-001",
            pack_id=pack_id,
            artifact_ids=[artifact_id],
            channels=["email"],
            limit=10,
        )
    )

    assert result["returned"] == 1
    assert result["summary"]["pack_id"] == pack_id
    assert result["summary"]["artifact_count"] == 2
    assert result["summary"]["sent"] == 1
    assert result["records"][0]["artifact_id"] == artifact_id
    assert result["records"][0]["channel"] == "email"
    assert reader.calls[0]["pack_id"] == pack_id
    assert reader.calls[0]["limit"] == 10
    assert reader.summary_calls[0]["pack_id"] == pack_id
