"""Shared models for workflow integration connectors."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ds_agent.domain.entities.external_reference import ExternalReference


class ConnectorResult(BaseModel):
    """Normalized result returned by external system connectors."""

    model_config = ConfigDict(frozen=True)

    success: bool
    external_ref: ExternalReference | None = None
    error_code: str | None = None
    error_message: str | None = None
    retriable: bool = False


class ConnectorHealthResult(BaseModel):
    """Health-check result for an integration connector."""

    model_config = ConfigDict(frozen=True)

    system: str
    healthy: bool
    message: str = ""
    latency_ms: float | None = None
