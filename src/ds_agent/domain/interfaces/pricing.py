"""Pricing port interface (Domain layer)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.messages import Usage


@runtime_checkable
class PricingPort(Protocol):
    """Cost calculation port — application layer depends on this abstraction."""

    def calculate_cost(self, model: str, usage: Usage) -> float: ...

    def track(self, model: str, usage: Usage) -> float: ...

    def get_summary(self) -> dict: ...
