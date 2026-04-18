"""SMTP email connector for workflow integration."""

from __future__ import annotations

import base64
import os
import smtplib
from datetime import UTC, datetime
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.entities.external_reference import ExternalReference
from ds_agent.infrastructure.external.connector_models import (
    ConnectorHealthResult,
    ConnectorResult,
)


class EmailAttachment(BaseModel):
    """One file attachment for an outbound email."""

    model_config = ConfigDict(frozen=True)

    filename: str = Field(min_length=1)
    content_base64: str = Field(min_length=1)
    content_type: str = "application/octet-stream"


class EmailRequest(BaseModel):
    """Request payload for sending one email via SMTP."""

    to: list[str] = Field(min_length=1)
    cc: list[str] = Field(default_factory=list)
    subject: str = Field(min_length=1)
    body_html: str = ""
    body_text: str = ""
    attachments: list[EmailAttachment] = Field(default_factory=list)
    reply_to: str | None = None
    from_address: str | None = None


class EmailConnector:
    """SMTP-based email sending connector."""

    system_name = "email"

    def __init__(
        self,
        *,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        default_from: str | None = None,
    ) -> None:
        self._smtp_host = (
            smtp_host or os.environ.get("DS_AGENT_EMAIL_SMTP_HOST") or ""
        )
        self._smtp_port = smtp_port or int(
            os.environ.get("DS_AGENT_EMAIL_SMTP_PORT", "587"),
        )
        self._username = (
            username or os.environ.get("DS_AGENT_EMAIL_SMTP_USERNAME") or ""
        )
        self._password = (
            password or os.environ.get("DS_AGENT_EMAIL_SMTP_PASSWORD") or ""
        )
        self._default_from = (
            default_from
            or os.environ.get("DS_AGENT_EMAIL_FROM_ADDRESS")
            or ""
        )

    def _is_configured(self) -> bool:
        return bool(self._smtp_host and self._default_from)

    def dispatch(
        self,
        request: EmailRequest,
        *,
        idempotency_key: str,
        dry_run: bool = False,
    ) -> ConnectorResult:
        now = datetime.now(UTC)
        sender = request.from_address or self._default_from

        if dry_run or not self._is_configured():
            return ConnectorResult(
                success=True,
                external_ref=ExternalReference(
                    system="email",
                    resource_type="message",
                    resource_id=idempotency_key,
                    metadata={
                        "to": request.to,
                        "subject": request.subject,
                        "simulated": not self._is_configured(),
                        "dry_run": dry_run,
                    },
                    created_at=now,
                    idempotency_key=idempotency_key,
                ),
            )

        try:
            msg = self._build_message(request, sender)
            recipients = request.to + request.cc
            with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
                server.starttls()
                if self._username:
                    server.login(self._username, self._password)
                server.sendmail(sender, recipients, msg.as_string())
            message_id = msg["Message-ID"] or idempotency_key
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
                system="email",
                resource_type="message",
                resource_id=str(message_id),
                metadata={
                    "to": request.to,
                    "subject": request.subject,
                    "sender": sender,
                },
                created_at=now,
                idempotency_key=idempotency_key,
            ),
        )

    def health_check(self) -> ConnectorHealthResult:
        """Check whether SMTP credentials are configured."""
        import time

        start = time.monotonic()
        if not self._is_configured():
            return ConnectorHealthResult(
                system=self.system_name,
                healthy=False,
                message="SMTP not configured (missing host/from).",
            )
        elapsed = (time.monotonic() - start) * 1000
        return ConnectorHealthResult(
            system=self.system_name,
            healthy=True,
            message=f"SMTP configured: {self._smtp_host}:{self._smtp_port}",
            latency_ms=round(elapsed, 1),
        )

    @staticmethod
    def _build_message(
        request: EmailRequest,
        sender: str,
    ) -> MIMEMultipart:
        msg = MIMEMultipart("mixed")
        msg["From"] = sender
        msg["To"] = ", ".join(request.to)
        if request.cc:
            msg["Cc"] = ", ".join(request.cc)
        msg["Subject"] = request.subject
        if request.reply_to:
            msg["Reply-To"] = request.reply_to

        alt = MIMEMultipart("alternative")
        if request.body_text:
            alt.attach(MIMEText(request.body_text, "plain", "utf-8"))
        if request.body_html:
            alt.attach(MIMEText(request.body_html, "html", "utf-8"))
        msg.attach(alt)

        for att in request.attachments:
            part = MIMEBase(*att.content_type.split("/", 1))
            part.set_payload(base64.b64decode(att.content_base64))
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=att.filename,
            )
            msg.attach(part)

        return msg
