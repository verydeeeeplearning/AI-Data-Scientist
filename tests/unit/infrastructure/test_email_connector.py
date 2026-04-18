"""Tests for EmailConnector dispatch and health check."""

from __future__ import annotations

from ds_agent.infrastructure.external.connector_models import (
    ConnectorHealthResult,
    ConnectorResult,
)
from ds_agent.infrastructure.external.email_connector import (
    EmailAttachment,
    EmailConnector,
    EmailRequest,
)


def test_email_dispatch_dry_run_returns_success() -> None:
    connector = EmailConnector()
    request = EmailRequest(
        to=["alice@example.com"],
        subject="Test",
        body_text="Hello",
    )
    result = connector.dispatch(request, idempotency_key="test-key", dry_run=True)
    assert isinstance(result, ConnectorResult)
    assert result.success is True
    assert result.external_ref is not None
    assert result.external_ref.system == "email"
    assert result.external_ref.resource_type == "message"
    assert result.external_ref.metadata.get("dry_run") is True


def test_email_dispatch_simulated_when_unconfigured() -> None:
    connector = EmailConnector(smtp_host="", default_from="")
    request = EmailRequest(
        to=["bob@example.com"],
        subject="Simulated",
        body_html="<p>Hi</p>",
    )
    result = connector.dispatch(request, idempotency_key="sim-key")
    assert result.success is True
    assert result.external_ref is not None
    assert result.external_ref.metadata.get("simulated") is True


def test_email_health_check_unconfigured() -> None:
    connector = EmailConnector(smtp_host="", default_from="")
    result = connector.health_check()
    assert isinstance(result, ConnectorHealthResult)
    assert result.system == "email"
    assert result.healthy is False
    assert "not configured" in result.message.lower()


def test_email_health_check_configured() -> None:
    connector = EmailConnector(
        smtp_host="smtp.example.com",
        default_from="agent@example.com",
    )
    result = connector.health_check()
    assert result.healthy is True
    assert "smtp.example.com" in result.message


def test_email_request_with_attachments() -> None:
    att = EmailAttachment(
        filename="report.csv",
        content_base64="SGVsbG8=",
        content_type="text/csv",
    )
    request = EmailRequest(
        to=["test@example.com"],
        subject="Report",
        body_text="See attached.",
        attachments=[att],
    )
    assert len(request.attachments) == 1
    assert request.attachments[0].filename == "report.csv"


def test_email_request_cc_and_reply_to() -> None:
    request = EmailRequest(
        to=["a@x.com"],
        cc=["b@x.com", "c@x.com"],
        subject="CC test",
        body_text="text",
        reply_to="reply@x.com",
    )
    assert request.cc == ["b@x.com", "c@x.com"]
    assert request.reply_to == "reply@x.com"
