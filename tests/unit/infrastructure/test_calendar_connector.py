"""Tests for CalendarConnector dispatch and health check."""

from __future__ import annotations

from ds_agent.infrastructure.external.calendar_connector import (
    CalendarConnector,
    CalendarEventRequest,
)
from ds_agent.infrastructure.external.connector_models import (
    ConnectorHealthResult,
    ConnectorResult,
)


def test_calendar_dispatch_dry_run_returns_success() -> None:
    connector = CalendarConnector()
    request = CalendarEventRequest(
        calendar_id="primary",
        summary="Team standup",
        start="2026-04-17T09:00:00",
        end="2026-04-17T09:30:00",
        timezone="Asia/Seoul",
    )
    result = connector.dispatch(request, idempotency_key="cal-key", dry_run=True)
    assert isinstance(result, ConnectorResult)
    assert result.success is True
    assert result.external_ref is not None
    assert result.external_ref.system == "calendar"
    assert result.external_ref.resource_type == "event"
    assert result.external_ref.metadata.get("dry_run") is True


def test_calendar_dispatch_simulated_when_unconfigured() -> None:
    connector = CalendarConnector(credentials_json="")
    request = CalendarEventRequest(
        calendar_id="primary",
        summary="Simulated meeting",
        start="2026-04-17T10:00:00",
        end="2026-04-17T11:00:00",
    )
    result = connector.dispatch(request, idempotency_key="sim-cal")
    assert result.success is True
    assert result.external_ref is not None
    assert result.external_ref.metadata.get("simulated") is True


def test_calendar_health_check_unconfigured() -> None:
    connector = CalendarConnector(credentials_json="")
    result = connector.health_check()
    assert isinstance(result, ConnectorHealthResult)
    assert result.system == "calendar"
    assert result.healthy is False
    assert "not configured" in result.message.lower()


def test_calendar_health_check_configured() -> None:
    connector = CalendarConnector(
        credentials_json='{"access_token": "fake-token"}',
    )
    result = connector.health_check()
    assert result.healthy is True
    assert "present" in result.message.lower()


def test_calendar_request_with_attendees_and_conference() -> None:
    request = CalendarEventRequest(
        calendar_id="team@group.calendar.google.com",
        summary="Sprint review",
        start="2026-04-18T14:00:00",
        end="2026-04-18T15:00:00",
        timezone="UTC",
        attendees_email=["alice@x.com", "bob@x.com"],
        conference_tool="meet",
    )
    assert len(request.attendees_email) == 2
    assert request.conference_tool == "meet"


def test_calendar_build_event_payload_includes_conference() -> None:
    connector = CalendarConnector()
    request = CalendarEventRequest(
        calendar_id="primary",
        summary="With Meet",
        start="2026-04-17T09:00:00",
        end="2026-04-17T09:30:00",
        conference_tool="meet",
    )
    payload = connector._build_event_payload(request)
    assert "conferenceData" in payload
    conf = payload["conferenceData"]["createRequest"]
    assert conf["conferenceSolutionKey"]["type"] == "hangoutsMeet"
