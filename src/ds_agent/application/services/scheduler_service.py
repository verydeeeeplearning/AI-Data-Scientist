"""Scheduler service for structured standing orders."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from ds_agent.application.ports.cron_runner_port import CronRunnerPort
from ds_agent.domain.entities.standing_order import CronTrigger, EventTrigger, StandingOrder


class StandingOrderStore(Protocol):
    """Persistence protocol for standing order scheduling."""

    def upsert_standing_order(self, order: StandingOrder) -> StandingOrder: ...
    def get_standing_order(self, order_id: str) -> StandingOrder | None: ...
    def list_standing_order_records(self, enabled: bool | None = None) -> list[StandingOrder]: ...
    def delete_standing_order(self, order_id: str) -> bool: ...
    def mark_standing_order_triggered(
        self,
        order_id: str,
        *,
        triggered_at: float | None = None,
        next_run_at: float | None = None,
        run_id: str | None = None,
    ) -> StandingOrder | None: ...
    def record_standing_order_result(
        self,
        order_id: str,
        *,
        status: str,
        summary: str,
        run_id: str | None = None,
        metadata: dict[str, object] | None = None,
        recorded_at: float | None = None,
    ) -> dict[str, object] | None: ...
    def list_standing_order_history(
        self,
        order_id: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, object]]: ...


class SchedulerService:
    """Application-layer orchestration for standing orders."""

    def __init__(
        self,
        *,
        store: StandingOrderStore,
        cron_runner: CronRunnerPort,
        record_runtime_event: Callable[..., object] | None = None,
    ) -> None:
        self._store = store
        self._cron_runner = cron_runner
        self._record_runtime_event = record_runtime_event

    def register(self, order: StandingOrder) -> StandingOrder:
        """Create or update one structured standing order."""
        order.updated_at = time.time()
        if isinstance(order.trigger, CronTrigger):
            reference = datetime.fromtimestamp(order.last_run_at or order.created_at, tz=UTC)
            next_run = self._cron_runner.next_run(order.trigger, after=reference)
            order.next_run_at = next_run.timestamp()
        else:
            order.next_run_at = None
        return self._store.upsert_standing_order(order)

    def unregister(self, order_id: str) -> bool:
        """Delete one standing order."""
        return self._store.delete_standing_order(order_id)

    def get_order(self, order_id: str) -> StandingOrder | None:
        """Return one standing order by id."""
        return self._store.get_standing_order(order_id)

    def list_orders(self, *, enabled: bool | None = None) -> list[StandingOrder]:
        """List standing orders."""
        return self._store.list_standing_order_records(enabled=enabled)

    def evaluate_triggers(
        self,
        *,
        now: datetime | None = None,
        event_kind: str | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> list[StandingOrder]:
        """Return standing orders that are due for the given schedule or event."""
        current = datetime.now(UTC) if now is None else self._ensure_utc(now)
        due: list[StandingOrder] = []

        for order in self._store.list_standing_order_records(enabled=True):
            trigger = order.trigger
            if isinstance(trigger, CronTrigger):
                if event_kind not in {None, "schedule.tick"}:
                    continue
                if self._is_cron_due(order, current=current):
                    due.append(order)
                continue

            if event_kind and isinstance(trigger, EventTrigger) and trigger.matches(
                event_kind, event_metadata
            ):
                due.append(order)

        due.sort(key=lambda item: item.created_at)
        return due

    def mark_dispatched(
        self,
        order_id: str,
        *,
        triggered_at: float | None = None,
        run_id: str | None = None,
    ) -> StandingOrder | None:
        """Mark one standing order as dispatched and advance its next run."""
        order = self._store.get_standing_order(order_id)
        if order is None:
            return None

        next_run_at = None
        trigger_time = time.time() if triggered_at is None else triggered_at
        if isinstance(order.trigger, CronTrigger):
            after = datetime.fromtimestamp(trigger_time, tz=UTC)
            next_run_at = self._cron_runner.next_run(order.trigger, after=after).timestamp()

        updated = self._store.mark_standing_order_triggered(
            order_id,
            triggered_at=trigger_time,
            next_run_at=next_run_at,
            run_id=run_id,
        )
        if updated is not None:
            self._record_result_event(updated, "dispatched", run_id=run_id)
        return updated

    def record_result(
        self,
        order_id: str,
        *,
        status: str,
        summary: str,
        run_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object] | None:
        """Record one standing-order execution result."""
        result = self._store.record_standing_order_result(
            order_id,
            status=status,
            summary=summary,
            run_id=run_id,
            metadata=metadata,
        )
        if result is not None:
            self._record_runtime_order_event(order_id, status, summary, run_id, metadata)
        return result

    def list_history(self, order_id: str, *, limit: int = 20) -> list[dict[str, object]]:
        """Return recent execution history for one order."""
        return self._store.list_standing_order_history(order_id, limit=limit)

    @staticmethod
    def build_prompt(order: StandingOrder) -> str:
        """Build the prompt dispatched by the autonomous runtime."""
        return order.build_prompt()

    def _is_cron_due(self, order: StandingOrder, *, current: datetime) -> bool:
        trigger = order.trigger
        if not isinstance(trigger, CronTrigger):
            return False

        next_run_at = order.next_run_at
        if next_run_at is None:
            reference = datetime.fromtimestamp(order.last_run_at or order.created_at, tz=UTC)
            next_run_at = self._cron_runner.next_run(trigger, after=reference).timestamp()
        return current.timestamp() >= next_run_at

    def _record_result_event(
        self,
        order: StandingOrder,
        status: str,
        *,
        run_id: str | None,
    ) -> None:
        self._record_runtime_order_event(
            order.order_id,
            status,
            f"Standing order '{order.name}' {status}.",
            run_id,
            {"standingOrderName": order.name},
        )

    def _record_runtime_order_event(
        self,
        order_id: str,
        status: str,
        summary: str,
        run_id: str | None,
        metadata: dict[str, object] | None,
    ) -> None:
        if self._record_runtime_event is None:
            return

        severity = "info"
        if status in {"succeeded", "completed"}:
            severity = "success"
        elif status in {"failed", "error"}:
            severity = "error"
        elif status in {"dispatched", "run_requested"}:
            severity = "warning"

        self._record_runtime_event(
            category="task",
            kind=f"standing_order.{status}",
            severity=severity,
            message=summary,
            source="standing_order",
            metadata={"standingOrderId": order_id, **dict(metadata or {})},
            run_id=run_id,
        )

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


_SCHEDULER_SERVICE: SchedulerService | None = None


def set_scheduler_service(service: SchedulerService | None) -> None:
    """Bind the process-global scheduler service used by standing-order tools."""
    global _SCHEDULER_SERVICE
    _SCHEDULER_SERVICE = service


def get_scheduler_service() -> SchedulerService:
    """Return the configured scheduler service."""
    if _SCHEDULER_SERVICE is None:
        raise RuntimeError("Scheduler service is not configured")
    return _SCHEDULER_SERVICE
