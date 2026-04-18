"""Domain value objects for drift monitoring."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class DriftMetric:
    """A single drift metric for one feature."""

    feature_name: str
    metric_type: str
    value: float
    threshold: float
    level: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DriftReport:
    """Aggregated drift report across multiple features."""

    metrics: list[DriftMetric]
    overall_status: str
    top_drifting_features: list[str]
    recommended_action: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, object]:
        return {
            "metrics": [metric.to_dict() for metric in self.metrics],
            "overall_status": self.overall_status,
            "top_drifting_features": self.top_drifting_features,
            "recommended_action": self.recommended_action,
            "timestamp": self.timestamp,
        }
