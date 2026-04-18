"""Google Calendar connector for workflow integration."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any, Literal
from urllib import error, request

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.entities.external_reference import ExternalReference
from ds_agent.infrastructure.external.connector_models import (
    ConnectorHealthResult,
    ConnectorResult,
)


class CalendarEventRequest(BaseModel):
    """Request payload for creating one calendar event."""

    model_config = ConfigDict(frozen=True)

    calendar_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    description: str = ""
    start: str = Field(min_length=1)
    end: str = Field(min_length=1)
    timezone: str = "UTC"
    attendees_email: list[str] = Field(default_factory=list)
    conference_tool: Literal["meet", "zoom", "teams"] | None = None


class CalendarConnector:
    """Google Calendar API connector (simulated when credentials absent)."""

    system_name = "calendar"

    def __init__(
        self,
        *,
        credentials_json: str | None = None,
        default_calendar_id: str | None = None,
    ) -> None:
        self._credentials_json = (
            credentials_json
            or os.environ.get("DS_AGENT_CALENDAR_CREDENTIALS_JSON")
            or ""
        )
        self._default_calendar_id = (
            default_calendar_id
            or os.environ.get("DS_AGENT_CALENDAR_ID")
            or "primary"
        )

    def _is_configured(self) -> bool:
        return bool(self._credentials_json)

    def dispatch(
        self,
        request_model: CalendarEventRequest,
        *,
        idempotency_key: str,
        dry_run: bool = False,
    ) -> ConnectorResult:
        now = datetime.now(UTC)

        if dry_run or not self._is_configured():
            return ConnectorResult(
                success=True,
                external_ref=ExternalReference(
                    system="calendar",
                    resource_type="event",
                    resource_id=idempotency_key,
                    metadata={
                        "summary": request_model.summary,
                        "start": request_model.start,
                        "end": request_model.end,
                        "simulated": not self._is_configured(),
                        "dry_run": dry_run,
                    },
                    created_at=now,
                    idempotency_key=idempotency_key,
                ),
            )

        try:
            event_payload = self._build_event_payload(request_model)
            result = self._create_event(
                request_model.calendar_id,
                event_payload,
            )
            event_id = str(
                result.get("id") or result.get("iCalUID") or idempotency_key,
            )
            event_link = result.get("htmlLink")
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
                system="calendar",
                resource_type="event",
                resource_id=event_id,
                url=event_link,
                metadata={
                    "summary": request_model.summary,
                    "start": request_model.start,
                    "end": request_model.end,
                    "attendees": request_model.attendees_email,
                },
                created_at=now,
                idempotency_key=idempotency_key,
            ),
        )

    def health_check(self) -> ConnectorHealthResult:
        """Check whether calendar credentials are configured."""
        if not self._is_configured():
            return ConnectorHealthResult(
                system=self.system_name,
                healthy=False,
                message="Calendar credentials not configured.",
            )
        return ConnectorHealthResult(
            system=self.system_name,
            healthy=True,
            message="Calendar credentials present.",
            latency_ms=0.0,
        )

    @staticmethod
    def _build_event_payload(
        req: CalendarEventRequest,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "summary": req.summary,
            "description": req.description,
            "start": {
                "dateTime": req.start,
                "timeZone": req.timezone,
            },
            "end": {
                "dateTime": req.end,
                "timeZone": req.timezone,
            },
        }
        if req.attendees_email:
            payload["attendees"] = [
                {"email": e} for e in req.attendees_email
            ]
        if req.conference_tool == "meet":
            payload["conferenceData"] = {
                "createRequest": {
                    "requestId": f"ds-agent-{req.summary[:20]}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                },
            }
        return payload

    def _create_event(
        self,
        calendar_id: str,
        event_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Call Google Calendar API to create an event."""
        creds = json.loads(self._credentials_json)
        access_token = creds.get("access_token") or creds.get("token", "")
        url = (
            f"https://www.googleapis.com/calendar/v3"
            f"/calendars/{calendar_id}/events"
        )
        data = json.dumps(event_payload).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=15) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise ValueError(
                f"Calendar API error ({exc.code}): {detail}",
            ) from exc
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise ValueError(f"Calendar API error: {parsed}")
        return parsed
