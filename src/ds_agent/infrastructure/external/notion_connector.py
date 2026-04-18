"""Notion connector wrapper for workflow integration."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib import error, request

from pydantic import BaseModel, Field

from ds_agent.domain.entities.external_reference import ExternalReference
from ds_agent.infrastructure.external.connector_models import ConnectorHealthResult, ConnectorResult
from ds_agent.infrastructure.external.document_converters import markdown_to_notion_blocks
from ds_agent.infrastructure.external.egress_guard import (
    is_egress_enabled,
    make_disabled_result,
)


class NotionPageRequest(BaseModel):
    """Request payload for creating one Notion page."""

    token: str
    title: str
    markdown_body: str
    parent_page_id: str | None = None
    database_id: str | None = None
    title_property: str = "title"
    api_base_url: str = "https://api.notion.com/v1"
    notion_version: str = "2022-06-28"
    properties: dict[str, Any] = Field(default_factory=dict)
    status: str | None = None
    owner: str | None = None
    quarter: str | None = None
    tags: list[str] = Field(default_factory=list)


class NotionConnector:
    """Basic Notion page-publishing connector."""

    system_name = "notion"

    def dispatch(
        self,
        request_model: NotionPageRequest,
        *,
        idempotency_key: str,
        dry_run: bool = False,
    ) -> ConnectorResult:
        now = datetime.now(UTC)
        if dry_run:
            return ConnectorResult(
                success=True,
                external_ref=ExternalReference(
                    system="notion",
                    resource_type="page",
                    resource_id=idempotency_key,
                    metadata={"dry_run": True},
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
            payload = self._request_json(request_model)
            page_id = str(payload.get("id") or idempotency_key)
            page_url = str(payload.get("url")) if payload.get("url") else None
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
                system="notion",
                resource_type="page",
                resource_id=page_id,
                url=page_url,
                metadata=payload,
                created_at=now,
                idempotency_key=idempotency_key,
            ),
        )

    def _request_json(self, request_model: NotionPageRequest) -> dict[str, Any]:
        resolved_parent = request_model.parent_page_id
        resolved_database = request_model.database_id
        if not resolved_parent and not resolved_database:
            raise ValueError("Notion parent page or database is not configured")
        properties: dict[str, Any] = {
            request_model.title_property: {
                "title": [{"type": "text", "text": {"content": request_model.title[:2000]}}]
            }
        }
        properties.update(request_model.properties)
        if request_model.status:
            properties["Status"] = {"select": {"name": request_model.status[:100]}}
        if request_model.owner:
            properties["Owner"] = {
                "rich_text": [{"type": "text", "text": {"content": request_model.owner[:200]}}]
            }
        if request_model.quarter:
            properties["Quarter"] = {
                "rich_text": [{"type": "text", "text": {"content": request_model.quarter[:100]}}]
            }
        if request_model.tags:
            properties["Tags"] = {
                "multi_select": [{"name": tag[:100]} for tag in request_model.tags if tag]
            }
        payload: dict[str, Any] = {
            "parent": (
                {"page_id": resolved_parent}
                if resolved_parent
                else {"database_id": resolved_database}
            ),
            "properties": properties,
            "children": markdown_to_notion_blocks(request_model.markdown_body),
        }
        req = request.Request(
            f"{request_model.api_base_url.rstrip('/')}/pages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {request_model.token}",
                "Content-Type": "application/json",
                "Notion-Version": request_model.notion_version,
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=10) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise ValueError(f"Notion API error ({exc.code}): {detail}") from exc
        parsed = json.loads(body)
        if not isinstance(parsed, dict) or parsed.get("object") == "error":
            raise ValueError(f"Notion API error: {parsed}")
        return parsed

    def health_check(self) -> ConnectorHealthResult:
        """Notion is stateless per-request — report available."""
        return ConnectorHealthResult(
            system=self.system_name,
            healthy=True,
            message="Stateless connector available.",
            latency_ms=0.0,
        )
