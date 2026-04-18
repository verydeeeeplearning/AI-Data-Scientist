"""Persistence contract for automatic regression-alert dispatch state."""

from __future__ import annotations

from typing import Protocol

from ds_agent.evaluation.domain.entities.regression_alert_state import (
    RegressionAlertDispatchState,
)


class RegressionAlertStateStore(Protocol):
    """Load/store the last dispatched alert fingerprint for one scope."""

    def get(self, dedupe_key: str) -> RegressionAlertDispatchState | None:
        """Return the latest dispatch state for one dedupe scope."""

    def upsert(self, state: RegressionAlertDispatchState) -> RegressionAlertDispatchState:
        """Persist one dispatch state."""

    def clear(self, dedupe_key: str) -> None:
        """Clear dispatch state when the alert set returns to healthy."""
