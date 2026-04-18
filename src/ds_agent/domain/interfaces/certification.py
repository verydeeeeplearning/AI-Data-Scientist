"""Persistence contract for autonomy certification state."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.certification import (
    AutonomyRunStat,
    CertificationRecord,
    CertificationStats,
)
from ds_agent.domain.value_objects.authority_mode import AuthorityMode


@runtime_checkable
class CertificationStore(Protocol):
    """Persistence contract for mission certification evidence and approvals."""

    def save_certification(self, record: CertificationRecord) -> None: ...

    def latest_certification(
        self,
        mission_name: str,
        *,
        mission_version: int | None = None,
    ) -> CertificationRecord | None: ...

    def list_certifications(
        self,
        mission_name: str,
        *,
        mission_version: int | None = None,
        limit: int = 20,
    ) -> list[CertificationRecord]: ...

    def is_certified(
        self,
        mission_name: str,
        level: AuthorityMode | str,
        *,
        mission_version: int | None = None,
    ) -> bool: ...

    def record_run_stat(self, stat: AutonomyRunStat) -> None: ...

    def stats_for(
        self,
        mission_name: str,
        *,
        mission_version: int | None = None,
    ) -> CertificationStats: ...
