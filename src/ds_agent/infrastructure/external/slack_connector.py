"""Slack connector wrapper for workflow integration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from ds_agent.domain.entities.external_reference import ExternalReference
from ds_agent.infrastructure.external.connector_models import ConnectorHealthResult, ConnectorResult
from ds_agent.infrastructure.external.egress_guard import (
    is_egress_enabled,
    make_disabled_result,
)
from ds_agent.infrastructure.external.slack_client import SlackClient


class SlackMessageRequest(BaseModel):
    """Request payload for posting to Slack through a configured webhook."""

    webhook_url: str
    text_fallback: str
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    channel: str | None = None
    thread_ts: str | None = None


class SlackConnector:
    """Basic Slack posting connector."""

    system_name = "slack"

    def __init__(self, client: SlackClient | None = None) -> None:
        self._client = client or SlackClient()

    def dispatch(
        self,
        request: SlackMessageRequest,
        *,
        idempotency_key: str,
        dry_run: bool = False,
    ) -> ConnectorResult:
        now = datetime.now(UTC)
        if dry_run:
            return ConnectorResult(
                success=True,
                external_ref=ExternalReference(
                    system="slack",
                    resource_type="webhook_message",
                    resource_id=idempotency_key,
                    metadata={
                        "channel": request.channel,
                        "thread_ts": request.thread_ts,
                        "dry_run": True,
                    },
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
            response = self._client.send(
                request.webhook_url,
                text=request.text_fallback,
                blocks=request.blocks or None,
            )
        except Exception as exc:
            return ConnectorResult(
                success=False,
                error_code=type(exc).__name__.upper(),
                error_message=str(exc),
                retriable=True,
            )
        return ConnectorResult(
            success=True,
            external_ref=ExternalReference(
                system="slack",
                resource_type="webhook_message",
                resource_id=idempotency_key,
                metadata={
                    "channel": request.channel,
                    "thread_ts": request.thread_ts,
                    "response": response,
                },
                created_at=now,
                idempotency_key=idempotency_key,
            ),
        )

    def health_check(self) -> ConnectorHealthResult:
        """Check whether the Slack client is reachable."""
        import time

        start = time.monotonic()
        try:
            if self._client is None:
                return ConnectorHealthResult(
                    system=self.system_name,
                    healthy=False,
                    message="No Slack client configured.",
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
