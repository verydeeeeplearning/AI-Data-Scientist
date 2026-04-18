from __future__ import annotations

from ds_agent.evaluation.domain.entities.regression_board import (
    RegressionAlert,
    RegressionBoardSnapshot,
    RegressionOverallSummary,
    RegressionWindowStats,
)
from ds_agent.evaluation.infrastructure.alerting_adapter import (
    SlackRegressionAlertNotifier,
    TeamsRegressionAlertNotifier,
)


def _snapshot() -> RegressionBoardSnapshot:
    return RegressionBoardSnapshot(
        total_records=6,
        recent_window=3,
        baseline_window_days=14,
        mode_filter="offline",
        domain_filter="retail",
        overall=RegressionOverallSummary(
            recent=RegressionWindowStats(record_count=3, avg_weighted_score=0.55, pass_rate=0.0),
            baseline=RegressionWindowStats(record_count=3, avg_weighted_score=0.87, pass_rate=1.0),
            delta_score=-0.32,
            delta_pass_rate=-1.0,
        ),
        alerts=(
            RegressionAlert(
                kind="pass_rate_drop",
                severity="high",
                scope="overall",
                message="Gold-suite pass rate dropped below the rolling baseline by more than 3pp.",
                current_value=0.0,
                baseline_value=1.0,
                delta=-1.0,
            ),
            RegressionAlert(
                kind="dimension_regression",
                severity="medium",
                scope="dimension",
                scope_key="scoping_accuracy",
                dimension="scoping_accuracy",
                message="Scoping Accuracy dropped below the rolling baseline by more than 5pp.",
                current_value=0.52,
                baseline_value=0.85,
                delta=-0.33,
            ),
        ),
    )


class _FakeSlackClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, list[dict[str, object]] | None]] = []

    def send(
        self,
        webhook_url: str,
        *,
        text: str,
        blocks: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        self.calls.append((webhook_url, text, blocks))
        return {"ok": True, "response": "slack-ok"}


class _FakeTeamsTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def post(self, webhook_url: str, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append((webhook_url, payload))
        return {"ok": True, "response": "teams-ok"}


def test_slack_regression_alert_notifier_builds_blocks_and_returns_delivery() -> None:
    client = _FakeSlackClient()
    notifier = SlackRegressionAlertNotifier(
        "https://hooks.slack.test/services/abc",
        client=client,
    )

    delivery = notifier.notify(snapshot=_snapshot(), alerts=_snapshot().alerts)

    webhook_url, text, blocks = client.calls[0]
    assert webhook_url == "https://hooks.slack.test/services/abc"
    assert "DS Agent Regression Board" in text
    assert delivery.channel == "slack"
    assert delivery.alert_count == 2
    assert delivery.response == "slack-ok"
    assert blocks is not None
    assert len(blocks) >= 2


def test_teams_regression_alert_notifier_builds_message_card_payload() -> None:
    transport = _FakeTeamsTransport()
    notifier = TeamsRegressionAlertNotifier(
        "https://teams.example.test/webhook",
        transport=transport,
    )

    delivery = notifier.notify(snapshot=_snapshot(), alerts=_snapshot().alerts)

    webhook_url, payload = transport.calls[0]
    assert webhook_url == "https://teams.example.test/webhook"
    assert payload["@type"] == "MessageCard"
    assert payload["title"] == "DS Agent Regression Alert"
    assert "DS Agent Regression Board" in str(payload["summary"])
    sections = payload["sections"]
    assert isinstance(sections, list)
    assert "Scoping Accuracy" in str(sections[0]["text"])
    assert delivery.channel == "teams"
    assert delivery.alert_count == 2
    assert delivery.response == "teams-ok"
