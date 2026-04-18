"""Budget domain value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class BudgetPolicy:
    """예산 정책 (불변 값 객체)."""

    max_iterations: int = 100
    max_total_tokens: int = 2_000_000
    max_cost_usd: float = 10.0
    max_wall_time_seconds: float = 7200.0
    warning_threshold_pct: float = 80.0
    critical_threshold_pct: float = 95.0


@dataclass
class BudgetState:
    """예산 현재 상태 (가변)."""

    iterations_used: int = 0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    wall_time_elapsed: float = 0.0
    warning_issued: bool = False
    critical_issued: bool = False


@dataclass
class BudgetThresholdEvent:
    """예산 임계값 도달 이벤트."""

    dimension: Literal["iterations", "tokens", "cost", "wall_time"]
    level: Literal["warning", "critical", "exhausted"]
    used: float
    limit: float
    pct: float
    message: str
