"""Dispatch regression-board alerts through configured notifiers."""
# mypy: disable-error-code="no-untyped-def"


from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from ds_agent.evaluation.application.dtos.regression_alert_dto import (
    RegressionAlertDispatchReport,
)
from ds_agent.evaluation.application.use_cases.build_regression_board import BuildRegressionBoard
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.entities.regression_alert_state import (
    RegressionAlertDispatchState,
)
from ds_agent.evaluation.domain.ports.regression_alert_notifier import RegressionAlertNotifier
from ds_agent.evaluation.domain.ports.regression_alert_state_store import RegressionAlertStateStore


class DispatchRegressionAlerts:
    """Build the latest regression board and send its active alerts."""

    def __init__(
        self,
        *,
        board_builder: BuildRegressionBoard,
        notifiers: Sequence[RegressionAlertNotifier],
        state_store: RegressionAlertStateStore | None = None,
    ) -> None:
        self._board_builder = board_builder
        self._notifiers = tuple(notifiers)
        self._state_store = state_store

    def execute(
        self,
        *,
        channels: Sequence[str] | None = None,
        axis: str = "commit",
        task_catalog: tuple[GoldTask, ...] | list[GoldTask] = (),
        mode: str | None = None,
        domain: str | None = None,
        task_id: str | None = None,
        limit: int | None = None,
        recent_window: int = 3,
        baseline_window_days: int = 14,
        skip_if_unchanged: bool = False,
        dispatch_source: str = "manual",
        dedupe_key: str = "global",
    ) -> RegressionAlertDispatchReport:
        snapshot = self._board_builder.execute(
            axis=axis,
            task_catalog=task_catalog,
            mode=mode,
            domain=domain,
            task_id=task_id,
            limit=limit,
            recent_window=recent_window,
            baseline_window_days=baseline_window_days,
        )
        fingerprint = _build_alert_fingerprint(snapshot)
        selected = _select_notifiers(self._notifiers, channels=channels)
        if not snapshot.alerts:
            if self._state_store is not None:
                self._state_store.clear(dedupe_key)
            return RegressionAlertDispatchReport(snapshot=snapshot, fingerprint=fingerprint)
        if skip_if_unchanged and self._state_store is not None:
            previous = self._state_store.get(dedupe_key)
            requested_channels = tuple(sorted(notifier.channel for notifier in selected))
            if previous is not None and previous.fingerprint == fingerprint and set(
                requested_channels
            ).issubset(previous.channels):
                return RegressionAlertDispatchReport(
                    snapshot=snapshot,
                    fingerprint=fingerprint,
                    skipped=True,
                    skip_reason="unchanged_fingerprint",
                )
        deliveries = tuple(
            notifier.notify(snapshot=snapshot, alerts=snapshot.alerts)
            for notifier in selected
            if snapshot.alerts
        )
        if self._state_store is not None and deliveries:
            self._state_store.upsert(
                RegressionAlertDispatchState(
                    dedupe_key=dedupe_key,
                    fingerprint=fingerprint,
                    channels=tuple(sorted(delivery.channel for delivery in deliveries)),
                    dispatch_source=dispatch_source,
                    alert_count=len(snapshot.alerts),
                    summary=deliveries[0].summary,
                )
            )
        return RegressionAlertDispatchReport(
            snapshot=snapshot,
            deliveries=deliveries,
            fingerprint=fingerprint,
        )


def _select_notifiers(
    notifiers: Sequence[RegressionAlertNotifier],
    *,
    channels: Sequence[str] | None,
) -> tuple[RegressionAlertNotifier, ...]:
    if not channels:
        return tuple(notifiers)
    wanted = {channel.strip().lower() for channel in channels if channel.strip()}
    return tuple(notifier for notifier in notifiers if notifier.channel in wanted)


def _build_alert_fingerprint(snapshot) -> str:
    payload = {
        "filters": {
            "mode": snapshot.mode_filter,
            "domain": snapshot.domain_filter,
        },
        "baselineSource": snapshot.baseline_source,
        "overall": {
            "deltaScore": snapshot.overall.delta_score,
            "deltaPassRate": snapshot.overall.delta_pass_rate,
        },
        "alerts": [
            {
                "kind": alert.kind,
                "severity": alert.severity,
                "scope": alert.scope,
                "scopeKey": alert.scope_key,
                "dimension": alert.dimension,
                "taskId": alert.task_id,
                "message": alert.message,
                "delta": alert.delta,
                "currentValue": alert.current_value,
                "baselineValue": alert.baseline_value,
            }
            for alert in snapshot.alerts
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
