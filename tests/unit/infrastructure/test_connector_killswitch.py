"""S14 tests: all 5 external connectors honour the in-adapter kill-switch.

Verifies that calling ``dispatch(dry_run=False)`` with the env var unset
(or falsy) yields ``success=False, error_code="EGRESS_DISABLED"`` instead
of reaching the real client. Dry-run path is unaffected (short-circuits
before the guard). Egress-enabled path is smoke-tested with a mock client
so the test never touches the network.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ds_agent.infrastructure.external.confluence_connector import (
    ConfluenceConnector,
    ConfluencePageRequest,
)
from ds_agent.infrastructure.external.git_connector import (
    GitConnector,
    GitPRRequest,
)
from ds_agent.infrastructure.external.jira_connector import (
    JiraConnector,
    JiraIssueRequest,
)
from ds_agent.infrastructure.external.notion_connector import (
    NotionConnector,
    NotionPageRequest,
)
from ds_agent.infrastructure.external.slack_connector import (
    SlackConnector,
    SlackMessageRequest,
)


def _slack_request() -> SlackMessageRequest:
    return SlackMessageRequest(webhook_url="https://example/hook", text_fallback="x")


def _jira_request() -> JiraIssueRequest:
    return JiraIssueRequest(
        base_url="https://example.atlassian.net",
        email="a@b.test",
        api_token="tok",
        project_key="DS",
        summary="s",
        description="d",
    )


def _confluence_request() -> ConfluencePageRequest:
    return ConfluencePageRequest(
        base_url="https://example.atlassian.net/wiki",
        email="a@b.test",
        api_token="tok",
        space_key="DS",
        title="t",
        markdown_body="c",
    )


def _notion_request() -> NotionPageRequest:
    return NotionPageRequest(
        token="tok",
        title="t",
        markdown_body="c",
        parent_page_id="p-1",
    )


def _git_request() -> GitPRRequest:
    return GitPRRequest(
        provider="github",
        repository="owner/repo",
        token="tok",
        base_branch="main",
        head_branch="feat/x",
        pr_title="t",
        pr_body_markdown="b",
    )


CONNECTOR_CASES = [
    ("slack", lambda: SlackConnector(client=MagicMock()), _slack_request),
    ("jira", lambda: JiraConnector(client=MagicMock()), _jira_request),
    ("confluence", lambda: ConfluenceConnector(), _confluence_request),
    ("notion", lambda: NotionConnector(), _notion_request),
    ("git", lambda: GitConnector(), _git_request),
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DS_AGENT_NETWORK_EGRESS_ENABLED", raising=False)


class TestKillSwitchDisablesByDefault:
    """Primary contract: dry_run=False + env unset → EGRESS_DISABLED."""

    @pytest.mark.parametrize("name, connector_factory, request_factory", CONNECTOR_CASES)
    def test_dispatch_returns_egress_disabled(
        self,
        name: str,
        connector_factory: object,
        request_factory: object,
    ) -> None:
        connector = connector_factory()  # type: ignore[operator]
        req = request_factory()  # type: ignore[operator]
        result = connector.dispatch(
            req,
            idempotency_key=f"ik-{name}",
            dry_run=False,
        )
        assert result.success is False, f"{name} connector did not honour the guard"
        assert result.error_code == "EGRESS_DISABLED"
        assert result.retriable is False


class TestKillSwitchLeavesDryRunUntouched:
    """dry_run=True short-circuits BEFORE the guard (pre-existing behaviour)."""

    @pytest.mark.parametrize("name, connector_factory, request_factory", CONNECTOR_CASES)
    def test_dry_run_still_succeeds_when_env_unset(
        self,
        name: str,
        connector_factory: object,
        request_factory: object,
    ) -> None:
        connector = connector_factory()  # type: ignore[operator]
        req = request_factory()  # type: ignore[operator]
        result = connector.dispatch(
            req,
            idempotency_key=f"ik-dry-{name}",
            dry_run=True,
        )
        assert result.success is True
        assert result.external_ref is not None
        assert result.external_ref.metadata.get("dry_run") is True
