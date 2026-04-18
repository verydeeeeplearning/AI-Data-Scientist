"""Support ports for workflow integration work objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ds_agent.domain.entities.approval_policy import DataSensitivity, PolicyDecisionType


@dataclass(frozen=True, slots=True)
class PolicyActionSpec:
    """Structured description of one outbound integration action."""

    action: str
    data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    environment: str = "dev"
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PolicyCheckResult:
    """Outcome of evaluating one outbound integration action."""

    decision: PolicyDecisionType
    reason: str
    decision_id: str


@runtime_checkable
class WorkflowIntegrationPolicyPort(Protocol):
    """Evaluate outbound workflow-integration actions against policy."""

    def check(self, spec: PolicyActionSpec) -> PolicyCheckResult: ...
