"""Application use cases for risk-tier matrix persistence + impact preview.

The risk-tier matrix lets operators map ``{action_name: {authority: tier}}``
labels onto the action-matrix. These use cases sit between the renderer (or
WS RPC layer) and the underlying ``JsonPolicyStore``-style port so the same
contract can be exercised by tests with a fake store.

The history-backed impact preview tallies how the candidate matrix would
have changed historical executions had it been the active matrix at that
point in time. The result is a coarse popularity vote per cell; the
renderer overlays this against its own renderer-only heuristic preview to
show "what changed" + "what historical traffic this would have re-tiered".
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from ds_agent.domain.entities.risk_tier_matrix import RiskTierMatrixSnapshot


class RiskTierMatrixStorePort(Protocol):
    """Storage port the risk-tier matrix use cases depend on.

    The protocol mirrors the subset of ``JsonPolicyStore`` we exercise.
    Tests can pass a fake; production wires the real store at the
    composition root.
    """

    def save_risk_tier_matrix(
        self,
        matrix: dict[str, dict[str, str]],
        *,
        saved_by: str | None = ...,
        saved_at: float | None = ...,
    ) -> RiskTierMatrixSnapshot: ...

    def load_risk_tier_matrix(self) -> dict[str, dict[str, str]]: ...

    def risk_tier_matrix_history(
        self, limit: int = ...
    ) -> list[RiskTierMatrixSnapshot]: ...


@dataclass(frozen=True, slots=True)
class LoadRiskTierMatrixOutput:
    """Current persisted matrix plus a slice of recent history."""

    matrix: Mapping[str, Mapping[str, str]]
    history: tuple[RiskTierMatrixSnapshot, ...]


class LoadRiskTierMatrixUseCase:
    """Return the current matrix and the last 10 history snapshots."""

    def __init__(self, store: RiskTierMatrixStorePort) -> None:
        self._store = store

    def execute(self) -> LoadRiskTierMatrixOutput:
        matrix = self._store.load_risk_tier_matrix()
        history = self._store.risk_tier_matrix_history(limit=10)
        return LoadRiskTierMatrixOutput(
            matrix=matrix,
            history=tuple(history),
        )


@dataclass(frozen=True, slots=True)
class SaveRiskTierMatrixInput:
    """Input accepted at the application boundary for matrix persistence."""

    matrix: Mapping[str, Mapping[str, str]]
    saved_by: str | None = None


class SaveRiskTierMatrixUseCase:
    """Validate matrix shape and persist it via the store port."""

    def __init__(self, store: RiskTierMatrixStorePort) -> None:
        self._store = store

    def execute(self, input: SaveRiskTierMatrixInput) -> RiskTierMatrixSnapshot:
        if not isinstance(input.matrix, Mapping):
            raise ValueError("matrix must be a mapping")

        coerced: dict[str, dict[str, str]] = {}
        for action_name, authority_map in input.matrix.items():
            action_key = str(action_name).strip()
            if not action_key:
                raise ValueError("matrix keys must be non-empty strings")
            if not isinstance(authority_map, Mapping):
                raise ValueError(
                    f"matrix entry for {action_key} must be a mapping"
                )
            row: dict[str, str] = {}
            for authority_name, tier_label in authority_map.items():
                authority_key = str(authority_name).strip()
                tier_value = str(tier_label).strip()
                if not authority_key or not tier_value:
                    raise ValueError(
                        f"matrix entries for {action_key} must use non-empty "
                        "authority/tier strings"
                    )
                row[authority_key] = tier_value
            if row:
                coerced[action_key] = row

        return self._store.save_risk_tier_matrix(
            coerced,
            saved_by=input.saved_by,
        )


@dataclass(frozen=True, slots=True)
class HistoryBackedImpactPreviewInput:
    """Input for `BuildHistoryBackedImpactPreview`."""

    candidate_matrix: Mapping[str, Mapping[str, str]]


@dataclass(frozen=True, slots=True)
class HistoryBackedImpactPreviewOutput:
    """Impact preview structure returned to the renderer."""

    added_rows: tuple[str, ...]
    removed_rows: tuple[str, ...]
    modified_rows: tuple[str, ...]
    historical_counts: Mapping[str, int] = field(default_factory=dict)


class BuildHistoryBackedImpactPreview:
    """Compare a candidate matrix against the live one + tally history.

    `addedRows` are action names present in the candidate but not in the
    persisted matrix; `removedRows` is the reverse; `modifiedRows` are
    action names whose authority -> tier mapping differs.

    `historicalCounts` totals tier occurrences per cell over the last 200
    history snapshots so the renderer can show "how often this cell has
    been tier X historically". The aggregate keys use the format
    ``"<action>.<authority>=<tier>"`` so the renderer can group them by
    cell without further parsing.
    """

    HISTORY_CAP = 200

    def __init__(self, store: RiskTierMatrixStorePort) -> None:
        self._store = store

    def execute(
        self, input: HistoryBackedImpactPreviewInput
    ) -> HistoryBackedImpactPreviewOutput:
        if not isinstance(input.candidate_matrix, Mapping):
            raise ValueError("candidate_matrix must be a mapping")

        current = self._store.load_risk_tier_matrix()
        candidate: dict[str, dict[str, str]] = {}
        for action_name, authority_map in input.candidate_matrix.items():
            action_key = str(action_name).strip()
            if not action_key or not isinstance(authority_map, Mapping):
                continue
            row: dict[str, str] = {}
            for authority_name, tier_label in authority_map.items():
                authority_key = str(authority_name).strip()
                tier_value = str(tier_label).strip()
                if authority_key and tier_value:
                    row[authority_key] = tier_value
            if row:
                candidate[action_key] = row

        added = tuple(sorted(set(candidate.keys()) - set(current.keys())))
        removed = tuple(sorted(set(current.keys()) - set(candidate.keys())))
        common = set(current.keys()) & set(candidate.keys())
        modified = tuple(
            sorted(
                action
                for action in common
                if dict(current[action]) != dict(candidate[action])
            )
        )

        history = self._store.risk_tier_matrix_history(limit=self.HISTORY_CAP)
        counts: Counter[str] = Counter()
        for snapshot in history:
            for action_name, authority_map in dict(snapshot.matrix).items():
                if not isinstance(authority_map, Mapping):
                    continue
                for authority_name, tier_label in authority_map.items():
                    key = (
                        f"{action_name}.{authority_name}={tier_label}"
                    )
                    counts[key] += 1

        return HistoryBackedImpactPreviewOutput(
            added_rows=added,
            removed_rows=removed,
            modified_rows=modified,
            historical_counts=dict(counts),
        )
