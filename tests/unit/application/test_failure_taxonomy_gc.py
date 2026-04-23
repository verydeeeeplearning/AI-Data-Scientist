from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ds_agent.application.learning.failure_taxonomy_gc import (
    FailureTaxonomyGCLoopUseCase,
)
from ds_agent.application.learning.harness_warning_ingestor import HarnessWarningIngestor
from ds_agent.domain.learning.failure_taxonomy import (
    FailureClass,
    FailureTaxonomyItem,
)
from ds_agent.domain.learning.learning_item import LearningItem, LearningItemStatus, LearningItemType, LearningItemType as LIT, SourceInfo
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore
from ds_agent.self_improve.promotion_candidates import JsonPromotionCandidateStore


@dataclass
class _FixedClock:
    now_value: datetime = datetime(2026, 4, 21, 9, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.now_value


def test_gc_usecase_classifies_warning_items_and_writes_report(tmp_path: Path) -> None:
    store = SqliteLearningStore(tmp_path / "learning.db")
    ingestor = HarnessWarningIngestor(store, _FixedClock())
    ingestor.ingest(
        {
            "type": "baseline_missing",
            "severity": "medium",
            "message": "No baseline established before model training",
        },
        session_id="session-1",
        run_id="run-1",
        surface="ws",
    )
    ingestor.ingest(
        {
            "type": "claim_traceability",
            "severity": "medium",
            "message": "Claims without evidence were detected",
        },
        session_id="session-2",
        run_id="run-2",
        surface="daemon",
    )

    result = FailureTaxonomyGCLoopUseCase(store, _FixedClock(), tmp_path).execute(
        promotion_threshold=3,
        limit=50,
    )

    assert result.total_items == 2
    assert result.total_recurrences == 2
    assert result.report_path is not None
    report_path = Path(result.report_path)
    assert report_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "missing_baseline" in report
    assert "narrative" in report

    items = store.list_items(item_type=LearningItemType.PATTERN)
    metadata_by_warning = {item.metadata["warningType"]: item.metadata for item in items}
    assert metadata_by_warning["baseline_missing"]["failureTaxonomyClass"] == "missing_baseline"
    assert metadata_by_warning["claim_traceability"]["failureTaxonomyClass"] == "narrative"


def test_gc_usecase_uses_recurrence_count_for_promotion_candidates(tmp_path: Path) -> None:
    store = SqliteLearningStore(tmp_path / "learning.db")
    ingestor = HarnessWarningIngestor(store, _FixedClock())

    for index in range(3):
        ingestor.ingest(
            {
                "type": "leakage",
                "severity": "high",
                "message": "Data leakage pattern detected",
            },
            session_id=f"session-{index}",
            run_id=f"run-{index}",
            surface="ws",
        )

    result = FailureTaxonomyGCLoopUseCase(store, _FixedClock(), tmp_path).execute(
        promotion_threshold=3,
        limit=50,
    )

    assert result.total_items == 1
    assert result.total_recurrences == 3
    assert result.promotion_candidate_classes == (FailureClass.LEAKAGE,)
    assert len(result.registered_skill_candidates) == 1
    assert result.registered_skill_candidates[0].candidate_id == "failure-taxonomy-leakage"

    item = store.list_items(item_type=LearningItemType.PATTERN, limit=10)[0]
    assert item.metadata["recurrenceCount"] == 3
    assert item.metadata["failureTaxonomyPromotionCandidate"] is True
    assert item.metadata["failureTaxonomyCandidateId"] == "failure-taxonomy-leakage"
    assert item.metadata["failureTaxonomyCandidateStatus"] == "pending_promotion"

    candidate_store = JsonPromotionCandidateStore.for_workspace(str(tmp_path))
    candidate = candidate_store.get("failure-taxonomy-leakage")
    assert candidate is not None
    assert candidate.status == "pending_promotion"
    assert Path(candidate.pending_path).exists()
    assert "Guardrail Draft" in Path(candidate.pending_path).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Gap 5D-4: remediation surface tests
# ---------------------------------------------------------------------------

def _make_learning_item(
    item_id: str,
    warning_type: str,
    recurrence_count: int = 1,
    extra_metadata: dict | None = None,
) -> LearningItem:
    """Build a minimal harness-warning LearningItem for testing."""
    now = datetime(2026, 4, 21, 9, 0, tzinfo=UTC)
    metadata: dict = {
        "warningType": warning_type,
        "severity": "high",
        "recurrenceCount": recurrence_count,
        "failureSourceKind": "harness.warning",
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return LearningItem(
        item_id=item_id,
        item_type=LearningItemType.PATTERN,
        status=LearningItemStatus.PROPOSED,
        title=f"Warning: {warning_type}",
        content=f"Observed {warning_type} failure",
        signature=f"sig-{item_id}",
        source=SourceInfo(),
        tags=["harness.warning"],
        created_at=now,
        updated_at=now,
        metadata=metadata,
    )


class TestRemediationSurfacesOnFailureTaxonomyItem:
    """Unit tests for remediation surface fields on FailureTaxonomyItem."""

    def test_from_learning_item_without_remediation_metadata_has_empty_surfaces(self) -> None:
        """An item with no remediationSurfaces metadata produces empty remediation_surfaces."""
        item = _make_learning_item("li-1", "leakage", recurrence_count=4)
        taxonomy = FailureTaxonomyItem.from_learning_item(item)

        assert taxonomy.remediation_surfaces == []
        assert taxonomy.owner is None
        assert taxonomy.target_artifact is None

    def test_from_learning_item_reads_remediation_surfaces_list(self) -> None:
        """remediationSurfaces list in metadata is projected correctly."""
        item = _make_learning_item(
            "li-2",
            "overfitting",
            recurrence_count=5,
            extra_metadata={
                "remediationSurfaces": ["verifier_check", "hook"],
                "remediationOwner": "ml-platform",
                "remediationTargetArtifact": "overfitting_check.py",
            },
        )
        taxonomy = FailureTaxonomyItem.from_learning_item(item)

        assert set(taxonomy.remediation_surfaces) == {"verifier_check", "hook"}
        assert taxonomy.owner == "ml-platform"
        assert taxonomy.target_artifact == "overfitting_check.py"

    def test_from_learning_item_reads_single_remediation_surface_fallback(self) -> None:
        """Single remediationSurface string is accepted via fallback key."""
        item = _make_learning_item(
            "li-3",
            "overfitting",
            extra_metadata={"remediationSurface": "docs_rule"},
        )
        taxonomy = FailureTaxonomyItem.from_learning_item(item)

        assert taxonomy.remediation_surfaces == ["docs_rule"]

    def test_from_learning_item_ignores_invalid_surface_values(self) -> None:
        """Unknown surface values are silently ignored."""
        item = _make_learning_item(
            "li-4",
            "leakage",
            extra_metadata={
                "remediationSurfaces": ["verifier_check", "unknown_surface", ""],
            },
        )
        taxonomy = FailureTaxonomyItem.from_learning_item(item)

        assert taxonomy.remediation_surfaces == ["verifier_check"]


class TestGCLoopIncompletePromotionCandidates:
    """Integration tests for incomplete promotion candidate detection in the GC loop."""

    def test_promotion_candidate_without_surface_is_incomplete(self, tmp_path: Path) -> None:
        """Promotion candidate class with no surface in any item is flagged incomplete."""
        store = SqliteLearningStore(tmp_path / "learning.db")
        ingestor = HarnessWarningIngestor(store, _FixedClock())

        for index in range(3):
            ingestor.ingest(
                {"type": "overfitting", "severity": "high", "message": "Overfitting detected"},
                session_id=f"s-{index}",
                run_id=f"r-{index}",
                surface="ws",
            )

        result = FailureTaxonomyGCLoopUseCase(store, _FixedClock(), tmp_path).execute(
            promotion_threshold=3,
        )

        assert FailureClass.OVERFITTING in result.promotion_candidate_classes
        assert FailureClass.OVERFITTING in result.incomplete_promotion_candidate_classes

    def test_promotion_candidate_with_surface_is_not_incomplete(self, tmp_path: Path) -> None:
        """Promotion candidate class whose items carry surfaces is not flagged incomplete."""
        store = SqliteLearningStore(tmp_path / "learning.db")
        ingestor = HarnessWarningIngestor(store, _FixedClock())

        for index in range(3):
            ingestor.ingest(
                {"type": "overfitting", "severity": "high", "message": "Overfitting detected"},
                session_id=f"s-{index}",
                run_id=f"r-{index}",
                surface="ws",
            )

        # Directly patch the stored item to have remediationSurfaces
        items = store.list_items(item_type=LearningItemType.PATTERN)
        assert items, "Expected at least one stored item"
        patched = items[0].model_copy(
            update={
                "metadata": {
                    **items[0].metadata,
                    "remediationSurfaces": ["verifier_check"],
                    "remediationOwner": "ml-team",
                    "remediationTargetArtifact": "overfitting_check.py",
                },
            }
        )
        store.save_item(patched)

        result = FailureTaxonomyGCLoopUseCase(store, _FixedClock(), tmp_path).execute(
            promotion_threshold=3,
        )

        assert FailureClass.OVERFITTING in result.promotion_candidate_classes
        assert FailureClass.OVERFITTING not in result.incomplete_promotion_candidate_classes

    def test_incomplete_candidate_logged_as_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """GC loop emits a log warning for promotion candidates without remediation surfaces."""
        store = SqliteLearningStore(tmp_path / "learning.db")
        ingestor = HarnessWarningIngestor(store, _FixedClock())

        for index in range(3):
            ingestor.ingest(
                {"type": "leakage", "severity": "high", "message": "Leakage detected"},
                session_id=f"s-{index}",
                run_id=f"r-{index}",
                surface="ws",
            )

        with caplog.at_level(logging.WARNING, logger="ds_agent.application.learning.failure_taxonomy_gc"):
            FailureTaxonomyGCLoopUseCase(store, _FixedClock(), tmp_path).execute(
                promotion_threshold=3,
            )

        assert any("leakage" in record.message and "no remediation surface" in record.message
                   for record in caplog.records)

    def test_report_contains_incomplete_marker_for_surface_missing_candidate(
        self, tmp_path: Path
    ) -> None:
        """GC report marks promotion candidates without surfaces as INCOMPLETE."""
        store = SqliteLearningStore(tmp_path / "learning.db")
        ingestor = HarnessWarningIngestor(store, _FixedClock())

        for index in range(3):
            ingestor.ingest(
                {"type": "leakage", "severity": "high", "message": "Leakage detected"},
                session_id=f"s-{index}",
                run_id=f"r-{index}",
                surface="ws",
            )

        result = FailureTaxonomyGCLoopUseCase(store, _FixedClock(), tmp_path).execute(
            promotion_threshold=3,
        )

        assert result.report_path is not None
        report = Path(result.report_path).read_text(encoding="utf-8")
        assert "INCOMPLETE (no remediation surface)" in report

    def test_report_contains_surface_info_for_complete_candidate(
        self, tmp_path: Path
    ) -> None:
        """GC report includes remediation surface details for candidates that have them."""
        store = SqliteLearningStore(tmp_path / "learning.db")
        ingestor = HarnessWarningIngestor(store, _FixedClock())

        for index in range(3):
            ingestor.ingest(
                {"type": "overfitting", "severity": "high", "message": "Overfitting detected"},
                session_id=f"s-{index}",
                run_id=f"r-{index}",
                surface="ws",
            )

        # Patch one item to carry a remediation surface
        items = store.list_items(item_type=LearningItemType.PATTERN)
        patched = items[0].model_copy(
            update={
                "metadata": {
                    **items[0].metadata,
                    "remediationSurfaces": ["contract_test"],
                    "remediationTargetArtifact": "test_overfitting_contract.py",
                },
            }
        )
        store.save_item(patched)

        result = FailureTaxonomyGCLoopUseCase(store, _FixedClock(), tmp_path).execute(
            promotion_threshold=3,
        )

        assert result.report_path is not None
        report = Path(result.report_path).read_text(encoding="utf-8")
        assert "contract_test" in report
        assert "test_overfitting_contract.py" in report
        # Should NOT be incomplete
        assert "overfitting [OK]" in report
