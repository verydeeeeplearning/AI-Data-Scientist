"""Scheduler adapter and status helpers for weekly learning-governance GC runs."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ds_agent.application.learning.failure_taxonomy_gc import (
    FailureTaxonomyGCLoopResult,
    FailureTaxonomyGCLoopUseCase,
    latest_gc_report_path,
)
from ds_agent.application.services.scheduler_service import SchedulerService
from ds_agent.domain.entities.standing_order import CronTrigger, StandingOrder
from ds_agent.domain.interfaces.learning import LearningStore
from ds_agent.domain.learning.learning_item import LearningItemStatus, LearningItemType
from ds_agent.runtime.learning_failure_signal_sync import PersistedFailureSignalSync

_IGNORED_LEARNING_STATUSES = frozenset(
    {
        LearningItemStatus.ARCHIVED,
        LearningItemStatus.DEPRECATED,
        LearningItemStatus.REJECTED,
    }
)


class LearningGovernancePolicyStore(Protocol):
    """Minimal policy-store surface needed for status inspection."""

    def get_standing_order(self, order_id: str) -> StandingOrder | None: ...
    def list_standing_order_history(
        self,
        order_id: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, object]]: ...


class LearningGovernanceScheduler:
    """Register and execute the periodic failure-taxonomy GC loop."""

    ORDER_ID = "learning_governance_weekly_gc"

    def __init__(
        self,
        *,
        scheduler_service: SchedulerService,
        store: LearningStore,
        workspace_dir: str | Path,
        cron: str = "0 9 * * MON",
        session_id: str = "learning:gc",
        promotion_threshold: int = 3,
        limit: int = 200,
    ) -> None:
        self._scheduler_service = scheduler_service
        self._store = store
        self._workspace_dir = Path(workspace_dir)
        self._cron = cron
        self._session_id = session_id
        self._promotion_threshold = max(1, int(promotion_threshold))
        self._limit = max(1, int(limit))

    def register(self) -> StandingOrder:
        """Create or update the standing order used for weekly GC sweeps."""

        existing = self._scheduler_service.get_order(self.ORDER_ID)
        created_at = existing.created_at if existing is not None else datetime.now(UTC).timestamp()
        updated_at = datetime.now(UTC).timestamp()
        order = StandingOrder(
            order_id=self.ORDER_ID,
            session_id=self._session_id,
            name="Learning Governance Weekly GC",
            description=(
                "Runs the failure-taxonomy GC loop over persisted governed failure-signal items "
                "and writes the weekly report."
            ),
            prompt=(
                "Run the weekly learning-governance GC loop, classify recurring failure signals, "
                "and persist the GC report."
            ),
            trigger=CronTrigger(self._cron, timezone="UTC"),
            scope={
                "system": "learning_governance",
                "job": "weekly_gc",
                "promotionThreshold": self._promotion_threshold,
                "limit": self._limit,
            },
            approval_gate="notify_only",
            created_at=created_at,
            updated_at=updated_at,
        )
        return self._scheduler_service.register(order)

    def run_due(self, *, now: datetime | None = None) -> FailureTaxonomyGCLoopResult | None:
        """Execute the GC loop when the registered cron trigger is due."""

        current = datetime.now(UTC) if now is None else _ensure_utc(now)
        due_orders = self._scheduler_service.evaluate_triggers(
            now=current,
            event_kind="schedule.tick",
        )
        if not any(order.order_id == self.ORDER_ID for order in due_orders):
            return None

        self._scheduler_service.mark_dispatched(
            self.ORDER_ID,
            triggered_at=current.timestamp(),
        )
        result = FailureTaxonomyGCLoopUseCase(
            self._store,
            _Clock(),
            self._workspace_dir,
            signal_sync=PersistedFailureSignalSync(
                store=self._store,
                workspace_dir=self._workspace_dir,
            ),
        ).execute(
            promotion_threshold=self._promotion_threshold,
            limit=self._limit,
            write_report=True,
        )
        self._scheduler_service.record_result(
            self.ORDER_ID,
            status="completed",
            summary=_summary_for_result(result),
            metadata={
                "totalItems": result.total_items,
                "totalRecurrences": result.total_recurrences,
                "promotionThreshold": result.promotion_threshold,
                "promotionCandidateClasses": [
                    failure_class.value for failure_class in result.promotion_candidate_classes
                ],
                "reportPath": result.report_path,
            },
        )
        return result


def build_learning_governance_status_payload(
    *,
    policy_store: LearningGovernancePolicyStore,
    store: LearningStore,
    workspace_dir: str | Path,
    history_limit: int = 5,
) -> dict[str, object]:
    """Return one read-only operational snapshot for learning governance."""

    workspace_path = Path(workspace_dir)
    PersistedFailureSignalSync(
        store=store,
        workspace_dir=workspace_path,
    ).sync(limit=500)
    order = policy_store.get_standing_order(LearningGovernanceScheduler.ORDER_ID)
    recent_history = policy_store.list_standing_order_history(
        LearningGovernanceScheduler.ORDER_ID,
        limit=max(1, history_limit),
    )
    latest_completed = next(
        (entry for entry in recent_history if str(entry.get("status") or "") == "completed"),
        None,
    )
    latest_report = latest_gc_report_path(workspace_path)
    warning_items = _list_active_warning_items(store)

    promotion_candidate_classes = sorted(
        {
            str(item.metadata.get("failureTaxonomyClass")).strip()
            for item in warning_items
            if item.metadata.get("failureTaxonomyPromotionCandidate") is True
            and str(item.metadata.get("failureTaxonomyClass") or "").strip()
        }
    )
    warning_types = sorted(
        {
            str(item.metadata.get("warningType")).strip()
            for item in warning_items
            if str(item.metadata.get("warningType") or "").strip()
        }
    )
    source_kinds = sorted(
        {
            str(item.metadata.get("failureSourceKind")).strip()
            for item in warning_items
            if str(item.metadata.get("failureSourceKind") or "").strip()
        }
    )
    failure_signal_types = sorted(
        {
            str(item.metadata.get("failureSignalType") or item.metadata.get("warningType")).strip()
            for item in warning_items
            if str(
                item.metadata.get("failureSignalType") or item.metadata.get("warningType") or ""
            ).strip()
        }
    )
    surfaces = sorted(
        {surface for item in warning_items for surface in _extract_surfaces(item.metadata)}
    )
    last_gc_at = max(
        (
            str(item.metadata.get("failureTaxonomyLastGcAt")).strip()
            for item in warning_items
            if str(item.metadata.get("failureTaxonomyLastGcAt") or "").strip()
        ),
        default=None,
    )
    backlog_payload = {
        "activeWarningItems": len(warning_items),
        "activeWarningRecurrences": sum(
            _read_recurrence_count(item.metadata) for item in warning_items
        ),
        "promotionCandidateItems": sum(
            1
            for item in warning_items
            if item.metadata.get("failureTaxonomyPromotionCandidate") is True
        ),
        "promotionCandidateClasses": promotion_candidate_classes,
        "warningTypes": warning_types,
        "failureSignalTypes": failure_signal_types,
        "sourceKinds": source_kinds,
        "surfaces": surfaces,
        "lastGcAt": last_gc_at,
    }

    return {
        "standingOrder": _serialize_standing_order(order),
        "backlog": backlog_payload,
        "latestCompletedRun": _serialize_history_entry(latest_completed),
        "latestReport": (
            {
                "path": str(latest_report),
                "name": latest_report.name,
            }
            if latest_report is not None
            else None
        ),
        "recentHistory": [
            payload
            for payload in (_serialize_history_entry(entry) for entry in recent_history)
            if payload is not None
        ],
    }


class _Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def _summary_for_result(result: FailureTaxonomyGCLoopResult) -> str:
    if result.total_items == 0:
        return "Learning governance weekly GC found no active governed failure-signal items."
    return (
        "Learning governance weekly GC classified "
        f"{result.total_items} item(s) across {result.total_recurrences} recurrence(s)."
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _list_active_warning_items(store: LearningStore):
    items = store.list_items(item_type=LearningItemType.PATTERN, limit=500)
    return [
        item
        for item in items
        if item.status not in _IGNORED_LEARNING_STATUSES
        and _is_failure_signal_item(item.metadata, item.tags)
    ]


def _is_failure_signal_item(metadata: Mapping[str, object], tags: list[str]) -> bool:
    if "harness.warning" in tags:
        return True
    warning_type = metadata.get("warningType")
    if isinstance(warning_type, str) and warning_type.strip() != "":
        return True
    signal_type = metadata.get("failureSignalType")
    return isinstance(signal_type, str) and signal_type.strip() != ""


def _read_recurrence_count(metadata: Mapping[str, object]) -> int:
    for key in ("failureTaxonomyRecurrenceCount", "recurrenceCount"):
        raw_value = metadata.get(key)
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return 1


def _extract_surfaces(metadata: Mapping[str, object]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in metadata.get("surfaces", []), [metadata.get("surface")]:
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if normalized and normalized not in seen:
                seen.append(normalized)
    return tuple(seen)


def _serialize_standing_order(order: StandingOrder | None) -> dict[str, object] | None:
    if order is None:
        return None
    trigger = order.trigger
    cron = trigger.cron if isinstance(trigger, CronTrigger) else None
    timezone = trigger.timezone if isinstance(trigger, CronTrigger) else None
    return {
        "orderId": order.order_id,
        "name": order.name,
        "enabled": order.enabled,
        "cron": cron,
        "timezone": timezone,
        "nextRunAt": _iso_from_timestamp(order.next_run_at),
        "lastRunAt": _iso_from_timestamp(order.last_run_at),
        "runCount": order.run_count,
        "failureCount": order.failure_count,
    }


def _serialize_history_entry(entry: Mapping[str, object] | None) -> dict[str, object] | None:
    if entry is None:
        return None
    metadata = entry.get("metadata")
    metadata_dict = dict(metadata) if isinstance(metadata, dict) else {}
    promotion_candidate_classes = metadata_dict.get("promotionCandidateClasses", [])
    if not isinstance(promotion_candidate_classes, list):
        promotion_candidate_classes = []
    return {
        "status": str(entry.get("status") or ""),
        "summary": str(entry.get("summary") or ""),
        "recordedAt": _iso_from_timestamp(entry.get("recorded_at")),
        "reportPath": metadata_dict.get("reportPath"),
        "totalItems": metadata_dict.get("totalItems"),
        "totalRecurrences": metadata_dict.get("totalRecurrences"),
        "promotionThreshold": metadata_dict.get("promotionThreshold"),
        "promotionCandidateClasses": [
            str(value)
            for value in promotion_candidate_classes
            if isinstance(value, str) and value.strip()
        ],
    }


def _iso_from_timestamp(value: object) -> str | None:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
