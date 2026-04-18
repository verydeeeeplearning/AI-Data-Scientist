"""Organization policy entities for team and enterprise controls."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class OrgRole(StrEnum):
    """Supported organization roles."""

    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


@dataclass(slots=True)
class Member:
    """One organization member."""

    user_id: str
    role: OrgRole
    display_name: str | None = None
    invited_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class OrgSettings:
    """Organization-level runtime policies."""

    allowed_providers: list[str] = field(default_factory=list)
    max_budget_usd_per_user: float | None = None
    max_budget_usd_per_org: float | None = None
    external_data_transfer_allowed: bool = True
    export_allowed: bool = True
    connector_creation_allowed: bool = True


@dataclass(slots=True)
class Organization:
    """Top-level organization model."""

    id: str
    name: str
    members: list[Member] = field(default_factory=list)
    settings: OrgSettings = field(default_factory=OrgSettings)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def get_member(self, user_id: str) -> Member | None:
        """Return one member by user id."""
        return next((member for member in self.members if member.user_id == user_id), None)

    def is_admin(self, user_id: str) -> bool:
        """Return whether the member is an admin."""
        member = self.get_member(user_id)
        return member is not None and member.role == OrgRole.ADMIN


@dataclass(slots=True)
class OrgUsageRecord:
    """One recorded usage event for organization budgets."""

    actor_id: str
    provider: str
    cost_usd: float
    model: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    cache_savings_usd: float = 0.0
    recorded_at: float = field(default_factory=time.time)
