"""Support ports for trust metadata projection use cases."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.approval import ApprovalRequest, ApprovalStatus
from ds_agent.domain.entities.certification import CertificationRecord
from ds_agent.domain.entities.lineage import LineageRecord
from ds_agent.domain.entities.post_deploy import PostDeployMonitorState
from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.runtime.runtime_event_log import RuntimeEventRecord


@runtime_checkable
class VerdictLookupPort(Protocol):
    """Read persisted verifier verdicts."""

    def list_for_task(self, task_id: str) -> list[ReviewVerdict]: ...

    def get(self, verdict_id: str) -> ReviewVerdict | None: ...


@runtime_checkable
class LineageLookupPort(Protocol):
    """Read persisted lineage records."""

    def get(self, record_id: str) -> LineageRecord | None: ...

    def latest_for_session(self, session_id: str) -> LineageRecord | None: ...


@runtime_checkable
class CertificationLookupPort(Protocol):
    """Read autonomy certification evidence."""

    def latest_certification(self, mission_name: str) -> CertificationRecord | None: ...


@runtime_checkable
class ApprovalLookupPort(Protocol):
    """Read persisted approval requests."""

    def get(self, approval_id: str) -> ApprovalRequest | None: ...

    def list(
        self,
        *,
        session_id: str | None = None,
        status: ApprovalStatus | None = None,
        limit: int = 20,
    ) -> list[ApprovalRequest]: ...


@runtime_checkable
class DeployMonitorLookupPort(Protocol):
    """Read post-deploy monitoring state."""

    def latest(self, model_id: str) -> PostDeployMonitorState | None: ...


@runtime_checkable
class RuntimeEventLookupPort(Protocol):
    """Read operator-visible runtime events."""

    def list(
        self,
        *,
        limit: int = 50,
        session_id: str | None = None,
        category: str | None = None,
    ) -> list[RuntimeEventRecord]: ...
