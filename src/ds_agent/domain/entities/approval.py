"""Domain entities for persisted approval requests."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ApprovalStatus(StrEnum):
    """Lifecycle states for approval requests."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(slots=True)
class ApprovalRequest:
    """One approval request created by ``ask_user`` and resolved by a control surface."""

    approval_id: str
    session_id: str
    run_id: str | None
    surface: str
    question: str
    kind: str = "generic"
    metadata: dict[str, Any] = field(default_factory=dict)
    options: list[str] = field(default_factory=list)
    default: str | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    response: str | None = None
    source: str | None = None
    actor: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    resolved_at: float | None = None
