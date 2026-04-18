"""Tests for integration connector health checks and IntegrationHub.health_check_all()."""

from __future__ import annotations

from ds_agent.infrastructure.external.confluence_connector import ConfluenceConnector
from ds_agent.infrastructure.external.connector_models import ConnectorHealthResult
from ds_agent.infrastructure.external.git_connector import GitConnector
from ds_agent.infrastructure.external.jira_connector import JiraConnector
from ds_agent.infrastructure.external.notion_connector import NotionConnector
from ds_agent.infrastructure.external.slack_connector import SlackConnector


def test_slack_connector_health_check_returns_healthy() -> None:
    connector = SlackConnector()
    result = connector.health_check()
    assert isinstance(result, ConnectorHealthResult)
    assert result.system == "slack"
    assert result.healthy is True
    assert result.latency_ms is not None


def test_jira_connector_health_check_returns_healthy() -> None:
    connector = JiraConnector()
    result = connector.health_check()
    assert result.system == "jira"
    assert result.healthy is True


def test_confluence_connector_health_check_returns_healthy() -> None:
    connector = ConfluenceConnector()
    result = connector.health_check()
    assert result.system == "confluence"
    assert result.healthy is True


def test_notion_connector_health_check_returns_healthy() -> None:
    connector = NotionConnector()
    result = connector.health_check()
    assert result.system == "notion"
    assert result.healthy is True


def test_git_connector_health_check_returns_healthy() -> None:
    connector = GitConnector()
    result = connector.health_check()
    assert result.system == "git"
    assert result.healthy is True


def test_integration_hub_health_check_all_returns_five_results() -> None:
    from unittest.mock import MagicMock

    from ds_agent.infrastructure.external.integration_hub import IntegrationHub

    store = MagicMock()
    clock = MagicMock()
    clock.now.return_value = None

    hub = IntegrationHub(store=store, clock=clock)
    results = hub.health_check_all()

    assert len(results) == 7
    systems = {r.system for r in results}
    assert systems == {"slack", "jira", "confluence", "notion", "git", "email", "calendar"}
    assert all(isinstance(r, ConnectorHealthResult) for r in results)
    # email and calendar are unconfigured by default, so not all healthy
    healthy_systems = {r.system for r in results if r.healthy}
    assert {"slack", "jira", "confluence", "notion", "git"} <= healthy_systems


def test_connector_health_result_model_serializes() -> None:
    result = ConnectorHealthResult(
        system="slack",
        healthy=True,
        message="OK",
        latency_ms=1.5,
    )
    data = result.model_dump(mode="json")
    assert data["system"] == "slack"
    assert data["healthy"] is True
    assert data["latency_ms"] == 1.5
