"""Domain entities tracking run lineage signals (rerun + promote).

These are pure data classes with no external dependencies. They model the
operator-visible artifacts that link result cards to delivery audiences and
the operator-named "rerun-from-step" linkage between two runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PromotedArtifactAudience = Literal["ds", "exec", "ml"]

PROMOTED_ARTIFACT_AUDIENCES: tuple[PromotedArtifactAudience, ...] = ("ds", "exec", "ml")


@dataclass(frozen=True, slots=True)
class PromotedArtifact:
    """One operator-promoted result card slated for a delivery audience.

    The artifact is not the rendered delivery pack itself — it is the
    lineage record that says "this card from this run is approved for this
    audience". Downstream delivery / packaging pipelines read these records
    to build the audience-specific outputs.
    """

    artifact_id: str
    run_id: str
    card_id: str
    audience: PromotedArtifactAudience
    title: str
    created_at: float
