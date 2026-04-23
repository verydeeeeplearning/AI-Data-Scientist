from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ds_agent.application.dtos.delivery import (
    DeliveryLogQueryResult,
    DeliveryLogSummary,
    DispatchLogRecord,
)
from ds_agent.application.services.mission_required_delivery_channels import (
    MissionRequiredDeliveryChannelResolver,
)
from ds_agent.domain.entities.delivery_pack import DeliveryChannel, DeliveryPack
from ds_agent.domain.entities.task_contract import TaskContract, TaskContractStatus
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.skills.mission_pack_loader import MissionPackLoader


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


def _bundle() -> TaskContractBundle:
    now = datetime(2026, 4, 21, tzinfo=UTC)
    bundle = TaskContractBundle(
        contract=TaskContract(
            task_id="TC-2026-001",
            session_id="session-1",
            type="analysis",
            status=TaskContractStatus.REVIEW,
            business_goal="Triage weekly KPI anomalies",
            mission="weekly-kpi-triage",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            ],
            created_at=now,
            updated_at=now,
        ),
        delivery_pack=DeliveryPack(
            pack_id="DP-1",
            task_id="TC-2026-001",
            generated_at=now,
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
        ),
    )
    return bundle.sync_references()


def _record(*, status: str) -> DispatchLogRecord:
    return DispatchLogRecord(
        task_id="TC-2026-001",
        pack_id="DP-1",
        artifact_id="ART-1",
        channel=DeliveryChannel.JIRA_TICKET,
        status=status,
        idempotency_key=f"key-{status}",
        recorded_at=datetime(2026, 4, 21, tzinfo=UTC),
    )


def test_weekly_kpi_triage_reports_missing_required_delivery_channel_until_dispatched() -> None:
    resolver = MissionRequiredDeliveryChannelResolver(
        MissionPackLoader(),
        StubDeliveryDispatchLogReader([]),
    )

    resolution = resolver.resolve_for_bundle(_bundle())

    assert resolution is not None
    assert resolution.mission_loaded is True
    assert resolution.dispatch_log_available is True
    assert resolution.required_delivery_channels == ("jira_ticket",)
    assert resolution.mapped_required_delivery_channels == {"jira_ticket": "jira_ticket"}
    assert resolution.unmapped_required_delivery_channels == ()
    assert resolution.satisfied_delivery_channels == ()
    assert resolution.missing_delivery_channels == ("jira_ticket",)


def test_weekly_kpi_triage_counts_sent_dispatch_as_satisfied() -> None:
    resolver = MissionRequiredDeliveryChannelResolver(
        MissionPackLoader(),
        StubDeliveryDispatchLogReader([_record(status="sent")]),
    )

    resolution = resolver.resolve_for_bundle(_bundle())

    assert resolution is not None
    assert resolution.satisfied_delivery_channels == ("jira_ticket",)
    assert resolution.missing_delivery_channels == ()


def test_duplicate_dispatch_counts_as_satisfied_delivery_channel() -> None:
    resolver = MissionRequiredDeliveryChannelResolver(
        MissionPackLoader(),
        StubDeliveryDispatchLogReader([_record(status="duplicate")]),
    )

    resolution = resolver.resolve_for_bundle(_bundle())

    assert resolution is not None
    assert resolution.satisfied_delivery_channels == ("jira_ticket",)
    assert resolution.missing_delivery_channels == ()
