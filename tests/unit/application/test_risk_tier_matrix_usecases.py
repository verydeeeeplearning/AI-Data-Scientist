"""Unit tests for risk-tier matrix application use cases.

These exercise the use-case layer in isolation by passing a fake
`RiskTierMatrixStorePort`, so they do not touch the filesystem and do
not depend on the JSON store implementation. The point is to verify
validation rules + impact-preview math.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from ds_agent.application.use_cases.risk_tier_matrix_usecases import (
    BuildHistoryBackedImpactPreview,
    HistoryBackedImpactPreviewInput,
    LoadRiskTierMatrixUseCase,
    SaveRiskTierMatrixInput,
    SaveRiskTierMatrixUseCase,
)
from ds_agent.domain.entities.risk_tier_matrix import RiskTierMatrixSnapshot


class _FakeStore:
    """Minimal in-memory implementation of `RiskTierMatrixStorePort`."""

    def __init__(
        self,
        *,
        initial_matrix: dict[str, dict[str, str]] | None = None,
        history: list[RiskTierMatrixSnapshot] | None = None,
    ) -> None:
        self._matrix: dict[str, dict[str, str]] = initial_matrix or {}
        self._history: list[RiskTierMatrixSnapshot] = list(history or [])
        self.save_calls: list[tuple[Mapping[str, Mapping[str, str]], str | None]] = []

    def save_risk_tier_matrix(
        self,
        matrix: dict[str, dict[str, str]],
        *,
        saved_by: str | None = None,
        saved_at: float | None = None,
    ) -> RiskTierMatrixSnapshot:
        self.save_calls.append((matrix, saved_by))
        snapshot = RiskTierMatrixSnapshot(
            saved_at=saved_at if saved_at is not None else 1234.5,
            matrix=dict(matrix),
            saved_by=saved_by,
        )
        self._matrix = dict(matrix)
        self._history.insert(0, snapshot)
        return snapshot

    def load_risk_tier_matrix(self) -> dict[str, dict[str, str]]:
        return {action: dict(row) for action, row in self._matrix.items()}

    def risk_tier_matrix_history(
        self, limit: int = 50
    ) -> list[RiskTierMatrixSnapshot]:
        return list(self._history[: max(int(limit), 0)])


class TestLoadRiskTierMatrixUseCase:
    def test_returns_current_and_recent_history(self):
        history = [
            RiskTierMatrixSnapshot(
                saved_at=2.0,
                matrix={"data_loader": {"supervised": "T1"}},
            ),
            RiskTierMatrixSnapshot(
                saved_at=1.0,
                matrix={"data_loader": {"supervised": "T0"}},
            ),
        ]
        store = _FakeStore(
            initial_matrix={"data_loader": {"supervised": "T1"}},
            history=history,
        )
        use_case = LoadRiskTierMatrixUseCase(store)

        result = use_case.execute()

        assert result.matrix == {"data_loader": {"supervised": "T1"}}
        assert len(result.history) == 2
        assert result.history[0].saved_at == 2.0


class TestSaveRiskTierMatrixUseCase:
    def test_persists_normalized_matrix(self):
        store = _FakeStore()
        use_case = SaveRiskTierMatrixUseCase(store)

        snapshot = use_case.execute(
            SaveRiskTierMatrixInput(
                matrix={"data_loader": {"supervised": "T1"}},
                saved_by="op@example.com",
            )
        )

        assert snapshot.matrix == {"data_loader": {"supervised": "T1"}}
        assert snapshot.saved_by == "op@example.com"
        assert store.save_calls == [
            ({"data_loader": {"supervised": "T1"}}, "op@example.com")
        ]

    def test_rejects_non_mapping_input(self):
        store = _FakeStore()
        use_case = SaveRiskTierMatrixUseCase(store)

        with pytest.raises(ValueError):
            use_case.execute(
                SaveRiskTierMatrixInput(matrix="not-a-mapping")  # type: ignore[arg-type]
            )

    def test_rejects_empty_action_key(self):
        store = _FakeStore()
        use_case = SaveRiskTierMatrixUseCase(store)

        with pytest.raises(ValueError):
            use_case.execute(
                SaveRiskTierMatrixInput(matrix={"   ": {"supervised": "T1"}})
            )


class TestBuildHistoryBackedImpactPreview:
    def test_classifies_added_removed_and_modified_rows(self):
        store = _FakeStore(
            initial_matrix={
                "data_loader": {"supervised": "T1"},
                "jira_create": {"autopilot": "T2"},
            },
        )
        use_case = BuildHistoryBackedImpactPreview(store)

        result = use_case.execute(
            HistoryBackedImpactPreviewInput(
                candidate_matrix={
                    "jira_create": {"autopilot": "T3"},
                    "prod_deploy": {"delegate": "T3"},
                },
            )
        )

        assert result.added_rows == ("prod_deploy",)
        assert result.removed_rows == ("data_loader",)
        assert result.modified_rows == ("jira_create",)

    def test_historical_counts_aggregate_across_snapshots(self):
        history = [
            RiskTierMatrixSnapshot(
                saved_at=3.0,
                matrix={"data_loader": {"supervised": "T1"}},
            ),
            RiskTierMatrixSnapshot(
                saved_at=2.0,
                matrix={"data_loader": {"supervised": "T1"}},
            ),
            RiskTierMatrixSnapshot(
                saved_at=1.0,
                matrix={"data_loader": {"supervised": "T0"}},
            ),
        ]
        store = _FakeStore(history=history)
        use_case = BuildHistoryBackedImpactPreview(store)

        result = use_case.execute(
            HistoryBackedImpactPreviewInput(candidate_matrix={})
        )

        assert result.historical_counts["data_loader.supervised=T1"] == 2
        assert result.historical_counts["data_loader.supervised=T0"] == 1

    def test_rejects_non_mapping_candidate(self):
        store = _FakeStore()
        use_case = BuildHistoryBackedImpactPreview(store)

        with pytest.raises(ValueError):
            use_case.execute(
                HistoryBackedImpactPreviewInput(
                    candidate_matrix="not-a-mapping",  # type: ignore[arg-type]
                )
            )

    def test_empty_candidate_with_no_history_returns_zero_impact(self):
        store = _FakeStore()
        use_case = BuildHistoryBackedImpactPreview(store)

        result = use_case.execute(
            HistoryBackedImpactPreviewInput(candidate_matrix={})
        )

        assert result.added_rows == ()
        assert result.removed_rows == ()
        assert result.modified_rows == ()
        assert result.historical_counts == {}
