"""Domain value objects for experimentation and A/B tests."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SampleSize:
    """Required sample size for an experiment design."""

    effect_size: float
    alpha: float
    power: float
    n_per_group: int
    total_n: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SRMResult:
    """Sample ratio mismatch check result."""

    p_value: float
    is_valid: bool
    expected_counts: tuple[float, float]
    observed_counts: tuple[int, int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentResult:
    """Statistical comparison result for an experiment."""

    metric_type: str
    control_mean: float
    treatment_mean: float
    effect_size: float
    p_value: float
    ci_low: float
    ci_high: float
    is_significant: bool
    winner: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EarlyStopDecision:
    """Decision for sequential testing."""

    should_stop: bool
    adjusted_alpha: float
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
