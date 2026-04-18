from __future__ import annotations

from ds_agent.evaluation.application.use_cases.dispatch_regression_alerts import (
    DispatchRegressionAlerts,
)
from ds_agent.evaluation.domain.entities.regression_alert_delivery import (
    RegressionAlertDelivery,
)
from ds_agent.evaluation.domain.entities.regression_alert_state import (
    RegressionAlertDispatchState,
)
from ds_agent.evaluation.domain.entities.regression_board import (
    RegressionAlert,
    RegressionBoardSnapshot,
    RegressionOverallSummary,
    RegressionWindowStats,
)


def _snapshot(*, alerts: tuple[RegressionAlert, ...]) -> RegressionBoardSnapshot:
    return RegressionBoardSnapshot(
        total_records=4,
        recent_window=3,
        baseline_window_days=14,
        overall=RegressionOverallSummary(
            recent=RegressionWindowStats(record_count=2, avg_weighted_score=0.55, pass_rate=0.5),
            baseline=RegressionWindowStats(
                record_count=2,
                avg_weighted_score=0.88,
                pass_rate=1.0,
            ),
            delta_score=-0.33,
            delta_pass_rate=-0.5,
        ),
        alerts=alerts,
    )


class _FakeBoardBuilder:
    def __init__(self, snapshot: RegressionBoardSnapshot) -> None:
        self.snapshot = snapshot
        self.calls: list[dict[str, object]] = []

    def execute(self, **kwargs) -> RegressionBoardSnapshot:
        self.calls.append(kwargs)
        return self.snapshot


class _FakeNotifier:
    def __init__(self, channel: str) -> None:
        self.channel = channel
        self.calls: list[tuple[RegressionAlert, ...]] = []

    def notify(
        self,
        *,
        snapshot: RegressionBoardSnapshot,
        alerts: tuple[RegressionAlert, ...],
    ) -> RegressionAlertDelivery:
        self.calls.append(alerts)
        return RegressionAlertDelivery(
            channel=self.channel,
            alert_count=len(alerts),
            target=f"{self.channel}-test",
            summary="ok",
        )


class _FakeAlertStateStore:
    def __init__(self) -> None:
        self.states: dict[str, RegressionAlertDispatchState] = {}

    def get(self, dedupe_key: str) -> RegressionAlertDispatchState | None:
        return self.states.get(dedupe_key)

    def upsert(self, state: RegressionAlertDispatchState) -> RegressionAlertDispatchState:
        self.states[state.dedupe_key] = state
        return state

    def clear(self, dedupe_key: str) -> None:
        self.states.pop(dedupe_key, None)


def test_dispatch_regression_alerts_filters_channels() -> None:
    snapshot = _snapshot(
        alerts=(
            RegressionAlert(
                kind="pass_rate_drop",
                severity="high",
                scope="overall",
                message="pass rate dropped",
                current_value=0.5,
                baseline_value=0.9,
                delta=-0.4,
            ),
        )
    )
    builder = _FakeBoardBuilder(snapshot)
    slack = _FakeNotifier("slack")
    teams = _FakeNotifier("teams")

    report = DispatchRegressionAlerts(board_builder=builder, notifiers=(slack, teams)).execute(
        channels=("teams",),
        axis="commit",
    )

    assert builder.calls[0]["axis"] == "commit"
    assert report.alert_count == 1
    assert report.delivered_channels == ("teams",)
    assert len(slack.calls) == 0
    assert len(teams.calls) == 1


def test_dispatch_regression_alerts_skips_delivery_when_no_alerts() -> None:
    builder = _FakeBoardBuilder(_snapshot(alerts=()))
    slack = _FakeNotifier("slack")
    state_store = _FakeAlertStateStore()
    state_store.upsert(
        RegressionAlertDispatchState(
            dedupe_key="mode=all::domain=all",
            fingerprint="previous",
            channels=("slack",),
            dispatch_source="runtime",
            alert_count=1,
            summary="old",
        )
    )

    report = DispatchRegressionAlerts(
        board_builder=builder,
        notifiers=(slack,),
        state_store=state_store,
    ).execute(dedupe_key="mode=all::domain=all")

    assert report.alert_count == 0
    assert report.deliveries == ()
    assert slack.calls == []
    assert state_store.get("mode=all::domain=all") is None


def test_dispatch_regression_alerts_skips_unchanged_fingerprint() -> None:
    snapshot = _snapshot(
        alerts=(
            RegressionAlert(
                kind="single_task_hard_fail",
                severity="high",
                scope="task",
                scope_key="retail.margin_watch.v1",
                task_id="retail.margin_watch.v1",
                message="retail.margin_watch.v1 fell below its task pass threshold.",
                current_value=0.42,
                baseline_value=0.6,
                delta=None,
            ),
        )
    )
    builder = _FakeBoardBuilder(snapshot)
    slack = _FakeNotifier("slack")
    state_store = _FakeAlertStateStore()
    use_case = DispatchRegressionAlerts(
        board_builder=builder,
        notifiers=(slack,),
        state_store=state_store,
    )

    first = use_case.execute(
        channels=("slack",),
        skip_if_unchanged=True,
        dispatch_source="runtime",
        dedupe_key="mode=all::domain=retail",
    )
    second = use_case.execute(
        channels=("slack",),
        skip_if_unchanged=True,
        dispatch_source="runtime",
        dedupe_key="mode=all::domain=retail",
    )

    assert first.skipped is False
    assert len(first.deliveries) == 1
    assert second.skipped is True
    assert second.skip_reason == "unchanged_fingerprint"
    assert second.deliveries == ()
    assert len(slack.calls) == 1
