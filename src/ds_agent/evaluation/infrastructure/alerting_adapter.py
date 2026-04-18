"""Webhook adapters for regression-board alerts."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib import parse, request

from ds_agent.evaluation.application.services.alerting_service import (
    build_regression_alert_lines,
    build_regression_alert_summary,
)
from ds_agent.evaluation.domain.entities.regression_alert_delivery import (
    RegressionAlertDelivery,
)
from ds_agent.evaluation.domain.entities.regression_board import (
    RegressionAlert,
    RegressionBoardSnapshot,
)
from ds_agent.infrastructure.external.slack_client import SlackClient


class SlackRegressionAlertNotifier:
    """Deliver regression alerts to a Slack webhook."""

    channel = "slack"

    def __init__(
        self,
        webhook_url: str,
        *,
        client: SlackClient | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._client = client or SlackClient()

    def notify(
        self,
        *,
        snapshot: RegressionBoardSnapshot,
        alerts: tuple[RegressionAlert, ...],
    ) -> RegressionAlertDelivery:
        summary = build_regression_alert_summary(snapshot=snapshot, alerts=alerts)
        blocks = _slack_blocks(snapshot=snapshot, alerts=alerts)
        response = self._client.send(self._webhook_url, text=summary, blocks=blocks)
        return RegressionAlertDelivery(
            channel="slack",
            alert_count=len(alerts),
            target=_target_label(self._webhook_url),
            summary=summary,
            alert_kinds=tuple(alert.kind for alert in alerts),
            response=str(response.get("response", "ok")),
        )


@dataclass(frozen=True)
class TeamsWebhookTransport:
    """Minimal Teams webhook transport."""

    def post(self, webhook_url: str, payload: dict[str, object]) -> dict[str, object]:
        req = request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
        return {"ok": True, "response": body}


class TeamsRegressionAlertNotifier:
    """Deliver regression alerts to a Teams webhook."""

    channel = "teams"

    def __init__(
        self,
        webhook_url: str,
        *,
        transport: TeamsWebhookTransport | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._transport = transport or TeamsWebhookTransport()

    def notify(
        self,
        *,
        snapshot: RegressionBoardSnapshot,
        alerts: tuple[RegressionAlert, ...],
    ) -> RegressionAlertDelivery:
        summary = build_regression_alert_summary(snapshot=snapshot, alerts=alerts)
        payload = _teams_payload(snapshot=snapshot, alerts=alerts, summary=summary)
        response = self._transport.post(self._webhook_url, payload)
        return RegressionAlertDelivery(
            channel="teams",
            alert_count=len(alerts),
            target=_target_label(self._webhook_url),
            summary=summary,
            alert_kinds=tuple(alert.kind for alert in alerts),
            response=str(response.get("response", "ok")),
        )


def build_configured_regression_alert_notifiers(
    environment: Mapping[str, str] | None = None,
) -> tuple[SlackRegressionAlertNotifier | TeamsRegressionAlertNotifier, ...]:
    """Build webhook notifiers from environment configuration."""

    env = dict(os.environ if environment is None else environment)
    notifiers: list[SlackRegressionAlertNotifier | TeamsRegressionAlertNotifier] = []
    slack_webhook = env.get("DS_AGENT_EVAL_SLACK_WEBHOOK_URL") or env.get(
        "DS_AGENT_SLACK_WEBHOOK_URL"
    )
    if slack_webhook:
        notifiers.append(SlackRegressionAlertNotifier(slack_webhook))
    teams_webhook = env.get("DS_AGENT_EVAL_TEAMS_WEBHOOK_URL")
    if teams_webhook:
        notifiers.append(TeamsRegressionAlertNotifier(teams_webhook))
    return tuple(notifiers)


def _slack_blocks(
    *,
    snapshot: RegressionBoardSnapshot,
    alerts: tuple[RegressionAlert, ...],
) -> list[dict[str, object]]:
    lines = build_regression_alert_lines(alerts=alerts, max_items=5)
    summary = build_regression_alert_summary(snapshot=snapshot, alerts=alerts)
    fields = [
        {
            "type": "mrkdwn",
            "text": (
                "*Recent score*\n"
                f"{_format_metric(snapshot.overall.recent.avg_weighted_score)}"
            ),
        },
        {
            "type": "mrkdwn",
            "text": (
                "*Baseline score*\n"
                f"{_format_metric(snapshot.overall.baseline.avg_weighted_score)}"
            ),
        },
        {
            "type": "mrkdwn",
            "text": (
                "*Recent pass rate*\n"
                f"{_format_metric(snapshot.overall.recent.pass_rate)}"
            ),
        },
        {
            "type": "mrkdwn",
            "text": (
                "*Baseline pass rate*\n"
                f"{_format_metric(snapshot.overall.baseline.pass_rate)}"
            ),
        },
    ]
    blocks: list[dict[str, object]] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary},
        },
        {"type": "section", "fields": fields},
    ]
    if lines:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(f"- {line}" for line in lines)},
            }
        )
    return blocks


def _teams_payload(
    *,
    snapshot: RegressionBoardSnapshot,
    alerts: tuple[RegressionAlert, ...],
    summary: str,
) -> dict[str, object]:
    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": summary,
        "themeColor": _teams_theme_color(alerts),
        "title": "DS Agent Regression Alert",
        "sections": [
            {
                "activityTitle": summary,
                "facts": [
                    {
                        "name": "Recent score",
                        "value": _format_metric(
                            snapshot.overall.recent.avg_weighted_score
                        ),
                    },
                    {
                        "name": "Baseline score",
                        "value": _format_metric(
                            snapshot.overall.baseline.avg_weighted_score
                        ),
                    },
                    {
                        "name": "Recent pass rate",
                        "value": _format_metric(snapshot.overall.recent.pass_rate),
                    },
                    {
                        "name": "Baseline pass rate",
                        "value": _format_metric(snapshot.overall.baseline.pass_rate),
                    },
                ],
                "text": "\n".join(build_regression_alert_lines(alerts=alerts, max_items=5)),
            }
        ],
    }


def _teams_theme_color(alerts: tuple[RegressionAlert, ...]) -> str:
    severities = {alert.severity for alert in alerts}
    if "high" in severities:
        return "D13438"
    if "medium" in severities:
        return "FF8C00"
    return "2EB886"


def _format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def _target_label(webhook_url: str) -> str:
    host = parse.urlsplit(webhook_url).netloc
    return host or "configured-webhook"
