"""Domain value object for retrain vs rollback decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class RemediationDecision:
    """Operational decision after drift or performance degradation."""

    decision: str
    severity: str
    rationale: str
    should_alert: bool
    recommended_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
