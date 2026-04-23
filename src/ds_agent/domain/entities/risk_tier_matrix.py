"""Domain entity for persisted authority x action-class risk-tier matrices.

A `RiskTierMatrixSnapshot` captures one operator-authored draft of the
risk-tier policy matrix (`{action_name: {authority_level: tier_label}}`)
along with the time it was saved and the optional actor who saved it.

Snapshots are immutable so they can be safely shared between threads and
appended to history logs without defensive copying.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RiskTierMatrixSnapshot:
    """One persisted draft of the risk-tier matrix."""

    saved_at: float
    matrix: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    saved_by: str | None = None
