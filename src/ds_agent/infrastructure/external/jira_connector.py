"""Jira connector wrapper for workflow integration."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, Field

from ds_agent.domain.entities.external_reference import ExternalReference
from ds_agent.infrastructure.external.connector_models import ConnectorHealthResult, ConnectorResult
from ds_agent.infrastructure.external.egress_guard import (
    is_egress_enabled,
    make_disabled_result,
)
from ds_agent.infrastructure.external.jira_client import JiraClient


class JiraIssueRequest(BaseModel):
    """Request payload for creating one Jira issue."""

    base_url: str
    email: str
    api_token: str
    project_key: str
    summary: str
    description: str
    issue_type: str = "Task"
    assignee: str | None = None
    priority: str | None = None
    labels: list[str] = Field(default_factory=list)
    due_date: date | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class JiraConnector:
    """Basic Jira issue-creation connector."""

    system_name = "jira"

    def __init__(self, client: JiraClient | None = None) -> None:
        self._client = client or JiraClient()

    def dispatch(
        self,
        request: JiraIssueRequest,
        *,
        idempotency_key: str,
        dry_run: bool = False,
    ) -> ConnectorResult:
        now = datetime.now(UTC)
        if dry_run:
            return ConnectorResult(
                success=True,
                external_ref=ExternalReference(
                    system="jira",
                    resource_type="issue",
                    resource_id=idempotency_key,
                    metadata={"dry_run": True, "project_key": request.project_key},
                    created_at=now,
                    idempotency_key=idempotency_key,
                ),
            )
        # S14 in-adapter egress kill-switch (RC-5 closed).
        if not is_egress_enabled():
            code, msg = make_disabled_result()
            return ConnectorResult(
                success=False,
                error_code=code,
                error_message=msg,
                retriable=False,
            )
        try:
            payload = self._client.create_issue(
                base_url=request.base_url,
                email=request.email,
                api_token=request.api_token,
                project=request.project_key,
                summary=request.summary,
                description=request.description,
                issue_type=request.issue_type,
                assignee=request.assignee,
                priority=request.priority,
                labels=request.labels,
            )
        except Exception as exc:
            return ConnectorResult(
                success=False,
                error_code=type(exc).__name__.upper(),
                error_message=str(exc),
                retriable=True,
            )
        issue_key = str(payload.get("key") or payload.get("id") or idempotency_key)
        issue_url = (
            None if not issue_key else f"{request.base_url.rstrip('/')}/browse/{issue_key}"
        )
        return ConnectorResult(
            success=True,
            external_ref=ExternalReference(
                system="jira",
                resource_type="issue",
                resource_id=issue_key,
                url=issue_url,
                metadata=payload,
                created_at=now,
                idempotency_key=idempotency_key,
            ),
        )

    def health_check(self) -> ConnectorHealthResult:
        """Check whether the Jira client is instantiated."""
        import time

        start = time.monotonic()
        try:
            if self._client is None:
                return ConnectorHealthResult(
                    system=self.system_name,
                    healthy=False,
                    message="No Jira client configured.",
                )
            elapsed = (time.monotonic() - start) * 1000
            return ConnectorHealthResult(
                system=self.system_name,
                healthy=True,
                message="Client available.",
                latency_ms=round(elapsed, 1),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return ConnectorHealthResult(
                system=self.system_name,
                healthy=False,
                message=str(exc),
                latency_ms=round(elapsed, 1),
            )
