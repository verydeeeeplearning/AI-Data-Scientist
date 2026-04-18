"""Domain entities for policy-based approval decisions."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum


class PolicyDecisionType(StrEnum):
    """Supported policy decisions."""

    AUTO = "auto"
    APPROVAL = "approval"
    DOUBLE_CHECK = "double_check"
    DENY = "deny"


class DataSensitivity(StrEnum):
    """Data sensitivity levels used by policy rules."""

    PUBLIC = "public"
    INTERNAL = "internal"
    PII = "pii"
    RESTRICTED = "restricted"


@dataclass(frozen=True, slots=True)
class PolicyRule:
    """One policy rule matched against a tool action."""

    action_pattern: str = "*"
    data_sensitivity: DataSensitivity | None = None
    environment: str | None = None
    confidence_threshold: float | None = None
    decision: PolicyDecisionType = PolicyDecisionType.AUTO

    def specificity(self) -> int:
        score = 0
        if self.action_pattern != "*":
            score += 1
        if self.data_sensitivity is not None:
            score += 1
        if self.environment is not None:
            score += 1
        if self.confidence_threshold is not None:
            score += 1
        return score


@dataclass(slots=True)
class StandingApproval:
    """Tracks repeated approvals promoted to automatic execution."""

    action: str
    data_sensitivity: DataSensitivity
    environment: str
    count: int = 0
    approved_by: list[str] = field(default_factory=list)
    promoted: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def key(self) -> str:
        return f"{self.action}|{self.data_sensitivity.value}|{self.environment}"


@dataclass(slots=True)
class ApprovalPolicy:
    """Complete policy document used by the evaluator."""

    rules: list[PolicyRule] = field(default_factory=list)
    standing_approvals: dict[str, StandingApproval] = field(default_factory=dict)
