from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from .access_policy import AccessAction
from .viewer_role import ViewerRole


@dataclass(frozen=True, slots=True)
class AccessLogEntry:
    """Redacted audit entry for one resource access decision."""

    resource_type: str
    resource_id: str
    action: AccessAction
    actor_ref: str
    allowed: bool
    role: ViewerRole | None = None
    reason: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)
