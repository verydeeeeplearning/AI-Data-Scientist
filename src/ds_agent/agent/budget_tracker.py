"""Iteration budget tracker."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ds_agent.domain.entities.messages import Usage
from ds_agent.domain.value_objects.budget import (
    BudgetPolicy,
    BudgetState,
    BudgetThresholdEvent,
)

if TYPE_CHECKING:
    from ds_agent.domain.interfaces.pricing import PricingPort


class IterationBudget:
    """Tracks iterations, tokens, cost, and wall time against budget policy."""

    def __init__(
        self,
        policy: BudgetPolicy | None = None,
        pricing: PricingPort | None = None,
    ) -> None:
        self.policy = policy or BudgetPolicy()
        self.state = BudgetState()
        if pricing is not None:
            self._pricing = pricing
        else:
            # Default: use concrete PricingTracker (backward compat)
            from ds_agent.providers.pricing import PricingTracker

            self._pricing = PricingTracker()
        self._start_time = time.monotonic()

    def consume(self, usage: Usage, model: str = "unknown") -> list[BudgetThresholdEvent]:
        """Record one iteration's usage. Returns threshold events if any."""
        self.state.iterations_used += 1
        self.state.total_tokens_used += usage.total_tokens

        cost = self._pricing.track(model, usage)
        self.state.total_cost_usd += cost
        self.state.wall_time_elapsed = time.monotonic() - self._start_time

        return self._check_thresholds()

    @property
    def is_exhausted(self) -> bool:
        return (
            self.state.iterations_used >= self.policy.max_iterations
            or self.state.total_tokens_used >= self.policy.max_total_tokens
            or self.state.total_cost_usd >= self.policy.max_cost_usd
            or self.state.wall_time_elapsed >= self.policy.max_wall_time_seconds
        )

    @property
    def remaining_iterations(self) -> int:
        return max(0, self.policy.max_iterations - self.state.iterations_used)

    @property
    def remaining_cost(self) -> float:
        return max(0.0, self.policy.max_cost_usd - self.state.total_cost_usd)

    def get_summary(self) -> dict:
        pricing_summary = self._pricing.get_summary()
        return {
            "iterations_used": self.state.iterations_used,
            "max_iterations": self.policy.max_iterations,
            "total_tokens_used": self.state.total_tokens_used,
            "max_total_tokens": self.policy.max_total_tokens,
            "total_cost_usd": self.state.total_cost_usd,
            "max_cost_usd": self.policy.max_cost_usd,
            "wall_time_seconds": self.state.wall_time_elapsed,
            "is_exhausted": self.is_exhausted,
            "cost_by_model": pricing_summary["by_model"],
        }

    def reset(self, policy: BudgetPolicy | None = None) -> None:
        """Reset mutable budget state for a fresh run."""
        if policy is not None:
            self.policy = policy
        self.state = BudgetState()
        self._start_time = time.monotonic()

        history = getattr(self._pricing, "history", None)
        if isinstance(history, list):
            history.clear()

        if hasattr(self._pricing, "total_cost_usd"):
            self._pricing.total_cost_usd = 0.0

    def _check_thresholds(self) -> list[BudgetThresholdEvent]:
        events: list[BudgetThresholdEvent] = []

        checks = [
            ("iterations", self.state.iterations_used, self.policy.max_iterations),
            ("tokens", self.state.total_tokens_used, self.policy.max_total_tokens),
            ("cost", self.state.total_cost_usd, self.policy.max_cost_usd),
            ("wall_time", self.state.wall_time_elapsed, self.policy.max_wall_time_seconds),
        ]

        for dimension, used, limit in checks:
            if limit <= 0:
                continue
            pct = (used / limit) * 100

            if pct >= 100:
                events.append(
                    BudgetThresholdEvent(
                        dimension=dimension,  # type: ignore[arg-type]
                        level="exhausted",
                        used=used,
                        limit=limit,
                        pct=pct,
                        message=f"{dimension} budget exhausted ({pct:.0f}%)",
                    )
                )
            elif pct >= self.policy.critical_threshold_pct and not self.state.critical_issued:
                self.state.critical_issued = True
                events.append(
                    BudgetThresholdEvent(
                        dimension=dimension,  # type: ignore[arg-type]
                        level="critical",
                        used=used,
                        limit=limit,
                        pct=pct,
                        message=f"{dimension} budget critical ({pct:.0f}%)",
                    )
                )
            elif pct >= self.policy.warning_threshold_pct and not self.state.warning_issued:
                self.state.warning_issued = True
                events.append(
                    BudgetThresholdEvent(
                        dimension=dimension,  # type: ignore[arg-type]
                        level="warning",
                        used=used,
                        limit=limit,
                        pct=pct,
                        message=f"{dimension} budget warning ({pct:.0f}%)",
                    )
                )

        return events
