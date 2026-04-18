"""Regression-board alert formatting helpers and dispatch orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.evaluation.domain.entities.regression_board import (
    RegressionAlert,
    RegressionBoardSnapshot,
)


class RegressionAlertPublisher(Protocol):
    """Send one formatted regression alert to an external channel."""

    channel: str

    def publish(
        self,
        *,
        title: str,
        summary: str,
        snapshot: RegressionBoardSnapshot,
    ) -> dict[str, object]: ...


class RegressionAlertDispatch(BaseModel):
    """One channel delivery outcome."""

    model_config = ConfigDict(frozen=True)

    channel: str = Field(min_length=1)
    delivered: bool
    response: dict[str, object] = Field(default_factory=dict)


class RegressionAlertDeliveryReport(BaseModel):
    """Aggregate delivery outcome for one board snapshot."""

    model_config = ConfigDict(frozen=True)

    delivered: bool
    alert_count: int = Field(ge=0)
    dispatched_count: int = Field(ge=0)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    dispatches: tuple[RegressionAlertDispatch, ...] = Field(default_factory=tuple)


class RegressionAlertingService:
    """Format and dispatch regression alerts only when the board is degraded."""

    def publish_snapshot(
        self,
        snapshot: RegressionBoardSnapshot,
        *,
        publishers: Sequence[RegressionAlertPublisher],
    ) -> RegressionAlertDeliveryReport:
        title, summary = self._format(snapshot)
        if not snapshot.alerts or not publishers:
            return RegressionAlertDeliveryReport(
                delivered=False,
                alert_count=len(snapshot.alerts),
                dispatched_count=0,
                title=title,
                summary=summary,
            )

        dispatches: list[RegressionAlertDispatch] = []
        for publisher in publishers:
            response = publisher.publish(title=title, summary=summary, snapshot=snapshot)
            dispatches.append(
                RegressionAlertDispatch(
                    channel=publisher.channel,
                    delivered=bool(response.get("ok", False)),
                    response=response,
                )
            )
        return RegressionAlertDeliveryReport(
            delivered=any(item.delivered for item in dispatches),
            alert_count=len(snapshot.alerts),
            dispatched_count=len(dispatches),
            title=title,
            summary=summary,
            dispatches=tuple(dispatches),
        )

    @staticmethod
    def _format(snapshot: RegressionBoardSnapshot) -> tuple[str, str]:
        recent = snapshot.overall.recent.avg_weighted_score
        baseline = snapshot.overall.baseline.avg_weighted_score
        delta = snapshot.overall.delta_score
        header = (
            f"Regression board alert: {len(snapshot.alerts)} active issue(s) "
            f"for mode={snapshot.mode_filter or 'all'} "
            f"domain={snapshot.domain_filter or 'all'}"
        )
        lines = [
            f"Recent score: {_metric(recent)}",
            f"Baseline score: {_metric(baseline)}",
            f"Delta: {_signed(delta)}",
            f"Records: {snapshot.total_records}",
        ]
        for alert in snapshot.alerts[:3]:
            scope = alert.scope_key or alert.dimension or alert.task_id or alert.scope
            lines.append(f"- [{alert.severity.upper()}] {scope}: {alert.message}")
        if len(snapshot.alerts) > 3:
            lines.append(f"- ... and {len(snapshot.alerts) - 3} more alert(s)")
        return header, "\n".join(lines)


def build_regression_alert_summary(
    *,
    snapshot: RegressionBoardSnapshot,
    alerts: Sequence[RegressionAlert],
) -> str:
    severity = "high" if any(item.severity == "high" for item in alerts) else "medium"
    return (
        f"DS Agent Regression Board [{severity.upper()}]: "
        f"{len(alerts)} active alert(s) "
        f"for mode={snapshot.mode_filter or 'all'} "
        f"domain={snapshot.domain_filter or 'all'} "
        f"(delta={_signed(snapshot.overall.delta_score)})."
    )


def build_regression_alert_lines(
    *,
    alerts: Sequence[RegressionAlert],
    max_items: int = 5,
) -> list[str]:
    lines: list[str] = []
    for alert in alerts[:max_items]:
        scope = _alert_scope_label(alert)
        lines.append(f"[{alert.severity.upper()}] {scope}: {alert.message}")
    if len(alerts) > max_items:
        lines.append(f"... and {len(alerts) - max_items} more alert(s)")
    return lines


def _alert_scope_label(alert: RegressionAlert) -> str:
    scope = alert.dimension or alert.scope_key or alert.task_id or alert.scope
    return scope.replace("_", " ").title()


def _metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def _signed(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.3f}"
