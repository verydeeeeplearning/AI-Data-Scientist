"""Confluence connector wrapper for workflow integration."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any
from urllib import error, request
from urllib.parse import urljoin

from pydantic import BaseModel, Field

from ds_agent.domain.entities.external_reference import ExternalReference
from ds_agent.infrastructure.external.connector_models import ConnectorHealthResult, ConnectorResult
from ds_agent.infrastructure.external.document_converters import markdown_to_confluence_storage
from ds_agent.infrastructure.external.egress_guard import (
    is_egress_enabled,
    make_disabled_result,
)


class ConfluencePageRequest(BaseModel):
    """Request payload for creating or updating one Confluence page."""

    base_url: str
    email: str
    api_token: str
    space_key: str
    title: str
    markdown_body: str
    parent_page_id: str | None = None
    labels: list[str] = Field(default_factory=list)
    version_comment: str | None = None
    overwrite_page_id: str | None = None


class ConfluenceConnector:
    """Basic Confluence page publishing connector."""

    system_name = "confluence"

    def dispatch(
        self,
        request_model: ConfluencePageRequest,
        *,
        idempotency_key: str,
        dry_run: bool = False,
    ) -> ConnectorResult:
        now = datetime.now(UTC)
        if dry_run:
            return ConnectorResult(
                success=True,
                external_ref=ExternalReference(
                    system="confluence",
                    resource_type="page",
                    resource_id=idempotency_key,
                    metadata={
                        "dry_run": True,
                        "space_key": request_model.space_key,
                        "labels": request_model.labels,
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
            if request_model.overwrite_page_id:
                payload = self._update_page(request_model)
            else:
                payload = self._create_page(request_model)
            page_id = str(payload.get("id") or idempotency_key)
            if request_model.labels:
                self._apply_labels(
                    request_model,
                    page_id=page_id,
                    labels=request_model.labels,
                )
            links = payload.get("_links")
            page_url = None
            if isinstance(links, dict) and links.get("webui"):
                page_url = urljoin(
                    request_model.base_url.rstrip("/") + "/",
                    str(links["webui"]).lstrip("/"),
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
                system="confluence",
                resource_type="page",
                resource_id=page_id,
                url=page_url,
                metadata=payload,
                created_at=now,
                idempotency_key=idempotency_key,
            ),
        )

    def _create_page(self, request_model: ConfluencePageRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "page",
            "title": request_model.title,
            "space": {"key": request_model.space_key},
            "body": {
                "storage": {
                    "value": markdown_to_confluence_storage(request_model.markdown_body),
                    "representation": "storage",
                }
            },
        }
        if request_model.parent_page_id:
            payload["ancestors"] = [{"id": request_model.parent_page_id}]
        return self._request_json(
            method="POST",
            url=f"{request_model.base_url.rstrip('/')}/rest/api/content",
            auth=self._basic_auth(request_model),
            payload=payload,
        )

    def _update_page(self, request_model: ConfluencePageRequest) -> dict[str, Any]:
        page_id = str(request_model.overwrite_page_id)
        current = self._request_json(
            method="GET",
            url=(
                f"{request_model.base_url.rstrip('/')}/rest/api/content/{page_id}"
                "?expand=version,space"
            ),
            auth=self._basic_auth(request_model),
            payload=None,
        )
        version = int(current.get("version", {}).get("number", 0)) + 1
        space_key = str(current.get("space", {}).get("key") or request_model.space_key)
        payload: dict[str, Any] = {
            "id": page_id,
            "type": "page",
            "title": request_model.title,
            "space": {"key": space_key},
            "version": {"number": version},
            "body": {
                "storage": {
                    "value": markdown_to_confluence_storage(request_model.markdown_body),
                    "representation": "storage",
                }
            },
        }
        if request_model.version_comment:
            payload["version"]["message"] = request_model.version_comment
        if request_model.parent_page_id:
            payload["ancestors"] = [{"id": request_model.parent_page_id}]
        return self._request_json(
            method="PUT",
            url=f"{request_model.base_url.rstrip('/')}/rest/api/content/{page_id}",
            auth=self._basic_auth(request_model),
            payload=payload,
        )

    def _apply_labels(
        self,
        request_model: ConfluencePageRequest,
        *,
        page_id: str,
        labels: list[str],
    ) -> dict[str, Any]:
        payload = [{"prefix": "global", "name": label[:255]} for label in labels if label]
        if not payload:
            return {}
        return self._request_json(
            method="POST",
            url=f"{request_model.base_url.rstrip('/')}/rest/api/content/{page_id}/label",
            auth=self._basic_auth(request_model),
            payload=payload,
        )

    @staticmethod
    def _basic_auth(request_model: ConfluencePageRequest) -> str:
        token = base64.b64encode(
            f"{request_model.email}:{request_model.api_token}".encode()
        ).decode("ascii")
        return f"Basic {token}"

    @staticmethod
    def _request_json(
        *,
        method: str,
        url: str,
        auth: str,
        payload: Any,
    ) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={
                "Authorization": auth,
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with request.urlopen(req, timeout=10) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise ValueError(f"Confluence API error ({exc.code}): {detail}") from exc
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise ValueError(f"Confluence API error: {parsed}")
        return parsed

    def health_check(self) -> ConnectorHealthResult:
        """Confluence is stateless per-request — report available."""
        return ConnectorHealthResult(
            system=self.system_name,
            healthy=True,
            message="Stateless connector available.",
            latency_ms=0.0,
        )
