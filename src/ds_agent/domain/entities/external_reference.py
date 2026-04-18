"""Typed references to resources created in external systems."""

from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha1
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ExternalSystem = Literal[
    "slack",
    "jira",
    "confluence",
    "notion",
    "github",
    "gitlab",
    "email",
    "calendar",
    "looker",
    "tableau",
    "asana",
    "monday",
]


def build_request_payload_hash(payload: Any) -> str:
    """Create a stable hash for idempotency discriminators and audit logs."""

    if isinstance(payload, str):
        normalized = payload
    else:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return sha1(normalized.encode("utf-8")).hexdigest()


def build_integration_idempotency_key(
    *,
    work_object_id: str,
    system: str,
    action: str,
    discriminator: str,
) -> str:
    """Build a spec-aligned idempotency key."""

    safe_discriminator = str(discriminator).replace(":", "-").strip() or "default"
    return f"wo_{work_object_id}:{system}:{action}:{safe_discriminator}"


class ExternalReference(BaseModel):
    """Pointer to a resource in an external collaboration system."""

    model_config = ConfigDict(frozen=True)

    system: ExternalSystem
    resource_type: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    idempotency_key: str = Field(min_length=1)

    @property
    def identity(self) -> str:
        return f"{self.system}:{self.resource_type}:{self.resource_id}"
